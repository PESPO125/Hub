import logging
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import imageio_ffmpeg
import yt_dlp
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import PluginRecord
from app.modules.plugins.registry import PluginRegistry

log = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])


class DownloadBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


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

    temporary = tempfile.TemporaryDirectory(prefix="youtube-dl-", dir=settings.data_dir)
    output_dir = Path(temporary.name)
    options = {
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(body.url, download=True)
            downloaded_path = Path(info.get("filepath") or downloader.prepare_filename(info))
        if not downloaded_path.is_file():
            raise FileNotFoundError("yt-dlp no produjo el archivo esperado")
    except yt_dlp.utils.DownloadError as exc:
        temporary.cleanup()
        detail = str(exc).replace(body.url, "[URL]").strip()
        log.warning("YouTube download failed: %s", detail)
        message = "No se pudo descargar ese video de YouTube."
        if detail:
            message = f"{message} Detalle: {detail[:400]}"
        raise AppError(422, "download_failed", message) from None
    except Exception as exc:
        temporary.cleanup()
        log.exception("YouTube download failed")
        raise AppError(500, "download_failed", "Ocurrió un error al descargar el video.") from exc

    return FileResponse(
        downloaded_path,
        filename=downloaded_path.name,
        media_type="application/octet-stream",
        background=BackgroundTask(temporary.cleanup),
    )