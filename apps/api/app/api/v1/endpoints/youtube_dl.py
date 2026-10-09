import logging
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import imageio_ffmpeg
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

log = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])


class DownloadBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    save_to_output_directory: bool = True


class YoutubeDownloaderSettings(BaseModel):
    output_directory: str = Field(min_length=1, max_length=1024)
    output_format: Literal["mp4", "webm", "mov", "mp3", "wav"] = "mp4"
    quality: Literal["best", "320", "256", "192", "128", "2160", "1440", "1080", "720", "480"] = "best"


def _hide_windows_directory(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attributes != -1:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attributes | 0x02)
    except (AttributeError, OSError):
        log.debug("No se pudo marcar como oculta la carpeta local de FFmpeg.", exc_info=True)


def _ensure_audio_ffmpeg(data_dir: Path) -> str | None:
    """Find FFmpeg or download a private local copy on demand for audio conversion."""
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, timeout=10)
        return None  # Let yt-dlp resolve the system executable through PATH.
    except (OSError, subprocess.SubprocessError):
        pass

    target_dir = data_dir / ".tools" / "ffmpeg"
    executable = target_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    target_dir.mkdir(parents=True, exist_ok=True)
    _hide_windows_directory(target_dir.parent)
    _hide_windows_directory(target_dir)

    if executable.is_file():
        try:
            subprocess.run([str(executable), "-version"], check=True, capture_output=True, timeout=10)
            return str(executable)
        except (OSError, subprocess.SubprocessError):
            executable.unlink(missing_ok=True)

    if os.name != "nt":
        # imageio-ffmpeg supplies a platform-specific executable for non-Windows installs.
        bundled = Path(imageio_ffmpeg.get_ffmpeg_exe())
        executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, executable)
        executable.chmod(executable.stat().st_mode | 0o111)
    else:
        archive_path = target_dir / "ffmpeg-download.zip"
        temporary_executable = target_dir / "ffmpeg-download.exe"
        release_api = "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest"
        try:
            request = urllib.request.Request(
                release_api,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Hub YouTube Downloader"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.load(response)
            asset = next(
                item for item in release.get("assets", [])
                if item.get("name", "").endswith("-essentials_build.zip")
            )
            download_url = asset["browser_download_url"]
            expected_checksum = asset.get("digest", "")
            if not expected_checksum.startswith("sha256:"):
                raise RuntimeError("GitHub no publicó un SHA-256 válido para el ZIP de FFmpeg.")
            expected_checksum = expected_checksum.removeprefix("sha256:").lower()
            if asset.get("size", 0) > 300 * 1024 * 1024:
                raise RuntimeError("El archivo de FFmpeg supera el tamaño permitido.")

            request = urllib.request.Request(download_url, headers={"User-Agent": "Hub YouTube Downloader"})
            with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as archive_file:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > 300 * 1024 * 1024:
                    raise RuntimeError("El archivo de FFmpeg supera el tamaño permitido.")
                downloaded_bytes = 0
                while chunk := response.read(1024 * 1024):
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > 300 * 1024 * 1024:
                        raise RuntimeError("El archivo de FFmpeg supera el tamaño permitido.")
                    archive_file.write(chunk)

            digest = hashlib.sha256()
            with archive_path.open("rb") as archive_file:
                while chunk := archive_file.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != expected_checksum:
                raise RuntimeError("La verificación SHA-256 del ZIP de FFmpeg falló.")

            with zipfile.ZipFile(archive_path) as archive:
                ffmpeg_member = next(
                    (name for name in archive.namelist() if name.lower().endswith("/bin/ffmpeg.exe")),
                    None,
                )
                if ffmpeg_member is None:
                    raise RuntimeError("El ZIP descargado no contiene ffmpeg.exe.")
                with archive.open(ffmpeg_member) as source, temporary_executable.open("wb") as destination:
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)

            subprocess.run([str(temporary_executable), "-version"], check=True, capture_output=True, timeout=20)
            temporary_executable.replace(executable)
        except (OSError, urllib.error.URLError, zipfile.BadZipFile, subprocess.SubprocessError, json.JSONDecodeError, StopIteration, KeyError) as exc:
            raise RuntimeError(f"No se pudo descargar o preparar FFmpeg: {exc}") from exc
        finally:
            archive_path.unlink(missing_ok=True)
            temporary_executable.unlink(missing_ok=True)

    try:
        subprocess.run([str(executable), "-version"], check=True, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"FFmpeg no quedó disponible en {executable}.") from exc
    return str(executable)


class DownloadCancelled(Exception):
    pass


def _validate_youtube_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        raise AppError(422, "invalid_video_url", "Introduce una URL HTTPS válida de YouTube.") from None
    allowed_host = host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    if parsed.scheme != "https" or not allowed_host or parsed.username or parsed.password:
        raise AppError(422, "invalid_video_url", "Introduce una URL HTTPS válida de YouTube.")


def _read_settings(db: Session, settings: Settings) -> YoutubeDownloaderSettings:
    preference = db.get(Preference, "youtube-dl-config")
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
    db.merge(Preference(key="youtube-dl-config", value=saved.model_dump()))
    db.commit()
    return saved.model_dump()


@router.post("/plugins/youtube-dl/download")
def download_youtube_video(
    body: DownloadBody,
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    settings: Settings = Depends(get_app_settings),
):
    _validate_youtube_url(body.url)
    plugin = registry.get("youtube-dl")
    if plugin is None or plugin.status != "available":
        raise AppError(404, "plugin_not_found", "El plugin de YouTube no está disponible.")
    record = db.get(PluginRecord, "youtube-dl")
    if record is None or record.admin_state != "enabled":
        raise AppError(409, "plugin_disabled", "Habilita el plugin antes de descargar videos.")
    active_task_id = db.scalar(select(Task.id).where(
        Task.plugin_id == "youtube-dl",
        Task.operation == "download-video",
        Task.status == "running",
    ).limit(1))
    if active_task_id is not None:
        raise AppError(409, "download_in_progress", "Ya hay una descarga en curso.")
    download_settings = _read_settings(db, settings)

    task = Task(
        id=str(uuid.uuid4()),
        plugin_id="youtube-dl",
        operation="download-video",
        status="running",
        message=("Descargando audio de YouTube." if download_settings.output_format in ("mp3", "wav") else "Descargando video de YouTube."),
    )
    db.add(task)
    db.commit()

    temporary = None
    stored_path: Path | None = None
    storage_key: str | None = None
    output_dir: Path | None = None
    files_dir = settings.data_dir / "files"

    last_progress_write = 0.0

    def report_progress(status: dict) -> None:
        nonlocal last_progress_write
        db.refresh(task)
        now = time.monotonic()
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = status.get("downloaded_bytes", 0)
            if now - last_progress_write >= 0.5 or task.cancel_requested:
                task.progress = min(downloaded / total, 0.99) if total else None
                speed = status.get("speed")
                speed_text = f" · {speed / 1_000_000:.2f} MB/s" if speed else ""
                task.message = f"Descargando {media_label}{speed_text}"
                db.commit()
                last_progress_write = now
        elif status.get("status") == "finished":
            task.progress = 0.99
            task.message = f"Procesando {media_label}."
            db.commit()
        if task.cancel_requested:
            raise DownloadCancelled

    output_format = download_settings.output_format
    audio_format = output_format in ("mp3", "wav")
    media_label = "audio" if audio_format else "video"
    try:
        if audio_format:
            task.message = "Comprobando FFmpeg y descargándolo si hace falta."
            db.commit()
            ffmpeg_location = _ensure_audio_ffmpeg(settings.data_dir)
        else:
            ffmpeg_location = imageio_ffmpeg.get_ffmpeg_exe()
        options = {
            "ffmpeg_location": ffmpeg_location,
            "noplaylist": True,
            "progress_hooks": [report_progress],
            "quiet": True,
            "no_warnings": True,
        }
        if audio_format:
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": output_format,
                "preferredquality": (
                    download_settings.quality
                    if download_settings.quality in ("320", "256", "192", "128")
                    else "320"
                ) if output_format == "mp3" else "0",
            }]
        else:
            height_filter = "" if download_settings.quality == "best" else f"[height<={download_settings.quality}]"
            source_video_ext, source_audio_ext = ("webm", "webm") if output_format == "webm" else ("mp4", "m4a")
            matching_formats = (
                f"bestvideo{height_filter}[ext={source_video_ext}]+bestaudio[ext={source_audio_ext}]"
                f"/best{height_filter}[ext={source_video_ext}]/best[ext={source_video_ext}]"
            )
            options["format"] = matching_formats
            postprocessor = "FFmpegVideoConvertor" if output_format == "mov" else "FFmpegVideoRemuxer"
            options["postprocessors"] = [{"key": postprocessor, "preferedformat": output_format}]
        temporary = tempfile.TemporaryDirectory(
            prefix="youtube-dl-",
            dir=settings.data_dir,
            ignore_cleanup_errors=True,
        )
        output_dir = Path(temporary.name)
        options["outtmpl"] = str(output_dir / "%(id)s.%(ext)s")
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(body.url, download=True)
            reported_paths = [
                info.get("filepath"),
                info.get("_filename"),
                downloader.prepare_filename(info),
            ]
            requested_downloads = info.get("requested_downloads") or []
            reported_paths.extend(item.get("filepath") for item in requested_downloads if isinstance(item, dict))
        # Prefer the requested final extension: reported paths can refer to
        # yt-dlp's pre-FFmpeg source file, which may still exist after conversion.
        candidates = [
            path for path in output_dir.rglob("*")
            if path.is_file() and not path.name.endswith((".part", ".ytdl"))
        ]
        downloaded_path = next((path for path in candidates if path.suffix.lower() == f".{output_format}"), None)
        if downloaded_path is None:
            downloaded_path = next(
                (Path(path) for path in reported_paths if path and Path(path).is_file()),
                None,
            )
        if downloaded_path is None and len(candidates) == 1:
            downloaded_path = candidates[0]
        db.refresh(task)
        if task.cancel_requested:
            raise DownloadCancelled
        if downloaded_path is None or not downloaded_path.is_file():
            raise FileNotFoundError("yt-dlp no produjo el archivo esperado")

        files_dir.mkdir(parents=True, exist_ok=True)
        file_id = str(uuid.uuid4())
        storage_key = f"{file_id}{downloaded_path.suffix}"
        stored_path = files_dir / storage_key
        os.replace(downloaded_path, stored_path)
        output_path = stored_path
        if body.save_to_output_directory:
            output_directory = Path(download_settings.output_directory)
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = output_directory / downloaded_path.name
            suffix = output_path.suffix
            stem = output_path.stem
            index = 1
            while output_path.exists():
                output_path = output_directory / f"{stem} ({index}){suffix}"
                index += 1
            if output_path.resolve() != stored_path.resolve():
                shutil.copy2(stored_path, output_path)
        size_bytes = stored_path.stat().st_size
        mime_type = mimetypes.guess_type(downloaded_path.name)[0] or "application/octet-stream"
        db.add(StoredFile(
            id=file_id,
            task_id=task.id,
            display_name=output_path.name if body.save_to_output_directory else downloaded_path.name,
            size_bytes=size_bytes,
            mime_type=mime_type,
            storage_key=storage_key,
        ))
        task.status = "completed"
        task.progress = 1.0
        if body.save_to_output_directory:
            task.message = f"{media_label.capitalize()} guardado en: {output_path}"
        else:
            task.message = f"Descarga de {media_label} completada."
        task.finished_at = utcnow()
        db.commit()
    except DownloadCancelled:
        task.status = "cancelled"
        task.message = "La descarga fue cancelada."
        task.error = {"code": "task_cancelled", "message": task.message}
        task.finished_at = utcnow()
        db.commit()
        raise AppError(409, "task_cancelled", task.message) from None
    except yt_dlp.utils.DownloadError as exc:
        detail = str(exc).replace(body.url, "[URL]").strip()
        log.warning("YouTube download failed: %s", detail)
        message = f"No se pudo descargar ese {media_label} de YouTube."
        if detail:
            message = f"{message} Detalle: {detail[:400]}"
        task.status = "failed"
        task.message = message
        task.error = {"code": "download_failed", "message": message}
        task.finished_at = utcnow()
        db.commit()
        raise AppError(422, "download_failed", message) from None
    except Exception as exc:
        if stored_path is not None and stored_path.exists():
            stored_path.unlink()
        log.exception("YouTube download failed")
        detail = str(exc).replace(body.url, "[URL]")
        for sensitive_path in (str(settings.data_dir), download_settings.output_directory):
            detail = detail.replace(sensitive_path, "[CARPETA]")
        detail = detail.strip()
        message = f"Ocurrió un error al descargar el {media_label}."
        if detail:
            message = f"{message} Detalle: {type(exc).__name__}: {detail[:300]}"
        task.status = "failed"
        task.message = message
        task.error = {"code": "download_failed", "message": message}
        task.finished_at = utcnow()
        db.commit()
        raise AppError(500, "download_failed", message) from exc
    finally:
        if temporary is not None:
            temporary.cleanup()

    return FileResponse(
        stored_path,
        filename=output_path.name if body.save_to_output_directory else downloaded_path.name,
        media_type=mime_type,
    )
