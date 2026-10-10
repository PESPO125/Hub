"""Construcción de las opciones de yt-dlp a partir de las preferencias del usuario."""
from __future__ import annotations

from collections.abc import Callable

AUDIO_FORMATS = ("mp3", "wav")
_AUDIO_BITRATES = ("320", "256", "192", "128")


def is_audio_format(output_format: str) -> bool:
    return output_format in AUDIO_FORMATS


def build_options(
    output_format: str,
    quality: str,
    *,
    ffmpeg_location: str | None,
    progress_hook: Callable[[dict], None],
    output_template: str,
) -> dict:
    options = {
        "ffmpeg_location": ffmpeg_location,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "outtmpl": output_template,
    }
    options.update(_audio_options(output_format, quality) if is_audio_format(output_format)
                   else _video_options(output_format, quality))
    return options


def _audio_options(output_format: str, quality: str) -> dict:
    # WAV es sin pérdida: el bitrate no aplica ("0" = mejor calidad).
    bitrate = (quality if quality in _AUDIO_BITRATES else "320") if output_format == "mp3" else "0"
    return {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format,
            "preferredquality": bitrate,
        }],
    }


def _video_options(output_format: str, quality: str) -> dict:
    height = "" if quality == "best" else f"[height<={quality}]"
    video_ext, audio_ext = ("webm", "webm") if output_format == "webm" else ("mp4", "m4a")
    selector = (
        f"bestvideo{height}[ext={video_ext}]+bestaudio[ext={audio_ext}]"
        f"/best{height}[ext={video_ext}]/best[ext={video_ext}]"
    )
    key = "FFmpegVideoConvertor" if output_format == "mov" else "FFmpegVideoRemuxer"
    return {"format": selector, "postprocessors": [{"key": key, "preferedformat": output_format}]}
