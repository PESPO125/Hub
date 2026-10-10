"""Built-in YouTube tool using Hub's installed yt-dlp/FFmpeg dependencies."""
from __future__ import annotations

import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import urlsplit

import truststore

truststore.inject_into_ssl()

import yt_dlp  # noqa: E402
from ffmpeg import resolve_ffmpeg_location  # noqa: E402
from options import build_options, is_audio_format  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PROTOCOL_STDOUT = sys.stdout


def emit(event: dict) -> None:
    # JSONL is always UTF-8; ensure_ascii also keeps redirected Windows stdout portable.
    PROTOCOL_STDOUT.write(json.dumps(event, ensure_ascii=True) + "\n")
    PROTOCOL_STDOUT.flush()


def download(request: dict) -> None:
    params = request.get("params") or {}
    config = request.get("config") or {}
    url = params.get("url", "")
    try:
        parsed = urlsplit(url) if isinstance(url, str) else None
        host = (parsed.hostname or "").lower().rstrip(".") if parsed else ""
    except ValueError:
        parsed, host = None, ""
    if (not parsed or parsed.scheme != "https" or parsed.username or parsed.password
            or not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"))):
        emit({"type": "error", "code": "invalid_video_url", "message": "Introduce una URL HTTPS válida de YouTube."})
        return

    output_format = config.get("output_format", "mp4")
    quality = config.get("quality", "best")
    if output_format not in {"mp4", "webm", "mov", "mp3", "wav"}:
        output_format = "mp4"
    media = "audio" if is_audio_format(output_format) else "video"
    work_dir = Path(request["work_dir"]).resolve()
    last_update = 0.0

    def progress(status: dict) -> None:
        nonlocal last_update
        now = time.monotonic()
        if status.get("status") == "downloading" and now - last_update >= 0.5:
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            value = min(status.get("downloaded_bytes", 0) / total, 0.99) if total else 0
            speed = status.get("speed")
            rate = f" · {speed / 1_000_000:.2f} MB/s" if speed else ""
            emit({"type": "progress", "value": value, "message": f"Descargando {media}{rate}"})
            last_update = now
        elif status.get("status") == "finished":
            emit({"type": "progress", "value": 0.99, "message": f"Procesando {media}."})

    try:
        data_dir = Path(config.get("_hub_data_dir", REPO / "data"))
        ffmpeg = resolve_ffmpeg_location(data_dir, audio_only=is_audio_format(output_format))
        options = build_options(
            output_format, quality, ffmpeg_location=ffmpeg, progress_hook=progress,
            output_template=str(work_dir / "%(id)s.%(ext)s"),
        )
        options["noplaylist"] = True
        # stdout is the JSON-lines protocol channel; keep incidental library output
        # away from it while emit() continues writing protocol events to its saved stream.
        with redirect_stdout(sys.stderr):
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.extract_info(url, download=True)
        candidates = [p for p in work_dir.iterdir() if p.is_file() and p.suffix.lower() == f".{output_format}"]
        if not candidates:
            raise FileNotFoundError("No se generó el formato solicitado.")
        path = candidates[0]
        emit({"type": "output", "path": path.name, "display_name": path.name})
        emit({"type": "done"})
    except yt_dlp.utils.DownloadError as exc:
        detail = str(exc).lower()
        if "not a bot" in detail and "sign in" in detail:
            message = "YouTube rechazó la solicitud y pide una verificación anti-bot. Inténtalo más tarde."
        else:
            message = f"No se pudo descargar el {media} de YouTube."
        emit({"type": "error", "code": "download_failed", "message": message})
    except Exception as exc:
        emit({"type": "error", "code": "download_failed", "message": f"Error preparando la descarga ({type(exc).__name__})."})


def main() -> None:
    try:
        request = json.loads(sys.stdin.readline())
        download(request)
    except Exception as exc:
        emit({"type": "error", "code": "invalid_request", "message": f"Solicitud inválida ({type(exc).__name__})."})


if __name__ == "__main__":
    main()
