import logging
import mimetypes
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yt_dlp
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import PluginRecord, Preference, StoredFile, Task, utcnow
from app.modules.plugins.registry import PluginRegistry
from app.modules.youtube.ffmpeg import resolve_ffmpeg_location
from app.modules.youtube.options import build_options, is_audio_format

log = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])

PLUGIN_ID = "youtube-dl"
OPERATION = "download-video"
SETTINGS_KEY = "youtube-dl-config"
PROGRESS_WRITE_INTERVAL = 0.5  # segundos entre escrituras de progreso en BD


class DownloadBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    save_to_output_directory: bool = True


class YoutubeDownloaderSettings(BaseModel):
    output_directory: str = Field(min_length=1, max_length=1024)
    output_format: Literal["mp4", "webm", "mov", "mp3", "wav"] = "mp4"
    quality: Literal["best", "320", "256", "192", "128", "2160", "1440", "1080", "720", "480"] = "best"


class DownloadCancelled(Exception):
    pass


# --------------------------------------------------------------------------- validación / ajustes

def _validate_youtube_url(url: str) -> None:
    error = AppError(422, "invalid_video_url", "Introduce una URL HTTPS válida de YouTube.")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        raise error from None
    allowed_host = host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    if parsed.scheme != "https" or not allowed_host or parsed.username or parsed.password:
        raise error


def _read_settings(db: Session, settings: Settings) -> YoutubeDownloaderSettings:
    preference = db.get(Preference, SETTINGS_KEY)
    if preference and isinstance(preference.value, dict):
        try:
            return YoutubeDownloaderSettings.model_validate(preference.value)
        except Exception:
            pass
    return YoutubeDownloaderSettings(output_directory=str(settings.data_dir / "downloads"))


@router.get("/plugins/youtube-dl/config")
def get_youtube_downloader_settings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    return _read_settings(db, settings).model_dump()


@router.put("/plugins/youtube-dl/config")
def put_youtube_downloader_settings(
    body: YoutubeDownloaderSettings,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    directory = Path(body.output_directory).expanduser()
    if not directory.is_absolute():
        directory = settings.data_dir / directory
    try:
        directory = directory.resolve()
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise AppError(422, "invalid_download_directory", "No se pudo crear la carpeta de descarga.") from None

    saved = body.model_copy(update={"output_directory": str(directory)})
    db.merge(Preference(key=SETTINGS_KEY, value=saved.model_dump()))
    db.commit()
    return saved.model_dump()


# --------------------------------------------------------------------------- precondiciones

def _require_enabled_plugin(db: Session, registry: PluginRegistry) -> None:
    plugin = registry.get(PLUGIN_ID)
    if plugin is None or plugin.status != "available":
        raise AppError(404, "plugin_not_found", "El plugin de YouTube no está disponible.")
    record = db.get(PluginRecord, PLUGIN_ID)
    if record is None or record.admin_state != "enabled":
        raise AppError(409, "plugin_disabled", "Habilita el plugin antes de descargar videos.")


def _reject_if_download_running(db: Session) -> None:
    running = db.scalar(select(Task.id).where(
        Task.plugin_id == PLUGIN_ID, Task.operation == OPERATION, Task.status == "running",
    ).limit(1))
    if running is not None:
        raise AppError(409, "download_in_progress", "Ya hay una descarga en curso.")


# --------------------------------------------------------------------------- tarea y progreso

def _close_task(db: Session, task: Task, status: str, message: str, error_code: str | None = None) -> None:
    task.status = status
    task.message = message
    task.error = {"code": error_code, "message": message} if error_code else None
    task.finished_at = utcnow()
    db.commit()


def _progress_hook(db: Session, task: Task, media_label: str):
    last_write = 0.0

    def hook(status: dict) -> None:
        nonlocal last_write
        db.refresh(task)  # recoge cancel_requested escrito por otra sesión
        kind = status.get("status")
        if kind == "downloading":
            now = time.monotonic()
            if now - last_write >= PROGRESS_WRITE_INTERVAL or task.cancel_requested:
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                task.progress = min(status.get("downloaded_bytes", 0) / total, 0.99) if total else None
                speed = status.get("speed")
                speed_text = f" · {speed / 1_000_000:.2f} MB/s" if speed else ""
                task.message = f"Descargando {media_label}{speed_text}"
                db.commit()
                last_write = now
        elif kind == "finished":
            task.progress = 0.99
            task.message = f"Procesando {media_label}."
            db.commit()
        if task.cancel_requested:
            raise DownloadCancelled

    return hook


# --------------------------------------------------------------------------- archivos

def _reported_paths(downloader, info: dict) -> list[str | None]:
    prepare_filename = getattr(downloader, "prepare_filename", None)
    prepared = prepare_filename(info) if callable(prepare_filename) else None
    paths = [info.get("filepath"), info.get("_filename"), prepared]
    paths.extend(d.get("filepath") for d in info.get("requested_downloads") or [] if isinstance(d, dict))
    return paths


def _locate_download(output_dir: Path, output_format: str, reported: list[str | None]) -> Path | None:
    """Prefiere la extensión final pedida: las rutas reportadas pueden apuntar al
    archivo previo a FFmpeg, que a veces sigue existiendo tras la conversión."""
    candidates = [p for p in output_dir.rglob("*") if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
    final = next((p for p in candidates if p.suffix.lower() == f".{output_format}"), None)
    if final:
        return final
    from_report = next((Path(p) for p in reported if p and Path(p).is_file()), None)
    if from_report:
        return from_report
    return candidates[0] if len(candidates) == 1 else None


def _copy_to_directory(source: Path, name: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    index = 1
    while destination.exists():
        destination = directory / f"{Path(name).stem} ({index}){Path(name).suffix}"
        index += 1
    shutil.copy2(source, destination)
    return destination


def _redact(text: str, url: str, *private_paths: str) -> str:
    text = text.replace(url, "[URL]")
    for path in private_paths:
        text = text.replace(path, "[CARPETA]")
    return text.strip()


# --------------------------------------------------------------------------- endpoint

@router.post("/plugins/youtube-dl/download")
def download_youtube_video(
    body: DownloadBody,
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    settings: Settings = Depends(get_app_settings),
):
    _validate_youtube_url(body.url)
    _require_enabled_plugin(db, registry)
    _reject_if_download_running(db)

    prefs = _read_settings(db, settings)
    audio = is_audio_format(prefs.output_format)
    media_label = "audio" if audio else "video"

    task = Task(id=str(uuid.uuid4()), plugin_id=PLUGIN_ID, operation=OPERATION, status="running",
                message=f"Descargando {media_label} de YouTube.")
    db.add(task)
    db.commit()

    temporary: tempfile.TemporaryDirectory | None = None
    stored_path: Path | None = None
    try:
        if audio:
            task.message = "Comprobando FFmpeg y descargándolo si hace falta."
            db.commit()
        ffmpeg_location = resolve_ffmpeg_location(settings.data_dir, audio_only=audio)

        temporary = tempfile.TemporaryDirectory(prefix="youtube-dl-", dir=settings.data_dir,
                                                ignore_cleanup_errors=True)
        output_dir = Path(temporary.name)
        options = build_options(
            prefs.output_format, prefs.quality,
            ffmpeg_location=ffmpeg_location,
            progress_hook=_progress_hook(db, task, media_label),
            output_template=str(output_dir / "%(id)s.%(ext)s"),
        )
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(body.url, download=True)
            reported = _reported_paths(downloader, info)

        downloaded = _locate_download(output_dir, prefs.output_format, reported)
        db.refresh(task)
        if task.cancel_requested:
            raise DownloadCancelled
        if downloaded is None:
            raise FileNotFoundError("yt-dlp no produjo el archivo esperado")

        files_dir = settings.data_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        file_id = str(uuid.uuid4())
        stored_path = files_dir / f"{file_id}{downloaded.suffix}"
        os.replace(downloaded, stored_path)

        display_name, saved_to = downloaded.name, None
        if body.save_to_output_directory:
            saved_to = _copy_to_directory(stored_path, downloaded.name, Path(prefs.output_directory))
            display_name = saved_to.name

        mime_type = mimetypes.guess_type(downloaded.name)[0] or "application/octet-stream"
        db.add(StoredFile(id=file_id, task_id=task.id, display_name=display_name,
                          size_bytes=stored_path.stat().st_size, mime_type=mime_type,
                          storage_key=stored_path.name))
        task.progress = 1.0
        message = (f"{media_label.capitalize()} guardado en: {saved_to}" if saved_to
                   else f"Descarga de {media_label} completada.")
        _close_task(db, task, "completed", message)
    except DownloadCancelled:
        message = "La descarga fue cancelada."
        _close_task(db, task, "cancelled", message, "task_cancelled")
        raise AppError(409, "task_cancelled", message) from None
    except yt_dlp.utils.DownloadError as exc:
        detail = _redact(str(exc), body.url)
        log.warning("YouTube download failed: %s", detail)
        message = f"No se pudo descargar ese {media_label} de YouTube."
        if detail:
            message = f"{message} Detalle: {detail[:400]}"
        _close_task(db, task, "failed", message, "download_failed")
        raise AppError(422, "download_failed", message) from None
    except Exception as exc:
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        log.exception("YouTube download failed")
        detail = _redact(str(exc), body.url, str(settings.data_dir), prefs.output_directory)
        message = f"Ocurrió un error al descargar el {media_label}."
        if detail:
            message = f"{message} Detalle: {type(exc).__name__}: {detail[:300]}"
        _close_task(db, task, "failed", message, "download_failed")
        raise AppError(500, "download_failed", message) from exc
    finally:
        if temporary is not None:
            temporary.cleanup()

    return FileResponse(stored_path, filename=display_name, media_type=mime_type)
