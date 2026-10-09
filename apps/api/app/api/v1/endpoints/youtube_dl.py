import logging
import mimetypes
import os
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import imageio_ffmpeg
import yt_dlp
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import PluginRecord, StoredFile, Task, utcnow
from app.modules.plugins.registry import PluginRegistry

log = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])


class DownloadBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


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

    task = Task(
        id=str(uuid.uuid4()),
        plugin_id="youtube-dl",
        operation="download-video",
        status="running",
        message="Descargando video de YouTube.",
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
                task.message = "Descargando video de YouTube."
                db.commit()
                last_progress_write = now
        elif status.get("status") == "finished":
            task.progress = 0.99
            task.message = "Procesando video."
            db.commit()
        if task.cancel_requested:
            raise DownloadCancelled

    options = {
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "noplaylist": True,
        "progress_hooks": [report_progress],
        "quiet": True,
        "no_warnings": True,
    }
    try:
        temporary = tempfile.TemporaryDirectory(
            prefix="youtube-dl-",
            dir=settings.data_dir,
            ignore_cleanup_errors=True,
        )
        output_dir = Path(temporary.name)
        options["outtmpl"] = str(output_dir / "%(id)s.%(ext)s")
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(body.url, download=True)
            downloaded_path = Path(info.get("filepath") or downloader.prepare_filename(info))
        db.refresh(task)
        if task.cancel_requested:
            raise DownloadCancelled
        if not downloaded_path.is_file():
            raise FileNotFoundError("yt-dlp no produjo el archivo esperado")

        files_dir.mkdir(parents=True, exist_ok=True)
        file_id = str(uuid.uuid4())
        storage_key = f"{file_id}{downloaded_path.suffix}"
        stored_path = files_dir / storage_key
        os.replace(downloaded_path, stored_path)
        size_bytes = stored_path.stat().st_size
        mime_type = mimetypes.guess_type(downloaded_path.name)[0] or "application/octet-stream"
        db.add(StoredFile(
            id=file_id,
            task_id=task.id,
            display_name=downloaded_path.name,
            size_bytes=size_bytes,
            mime_type=mime_type,
            storage_key=storage_key,
        ))
        task.status = "completed"
        task.progress = 1.0
        task.message = "Video descargado correctamente."
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
        message = "No se pudo descargar ese video de YouTube."
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
        message = "Ocurrió un error al descargar el video."
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
        filename=downloaded_path.name,
        media_type=mime_type,
    )