"""Localiza FFmpeg en el sistema o prepara una copia privada en ``data/.tools/ffmpeg``."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import imageio_ffmpeg

log = logging.getLogger(__name__)

_RELEASE_API = "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest"
_ASSET_SUFFIX = "-essentials_build.zip"
_USER_AGENT = "Hub YouTube Downloader"
_MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
_CHUNK_BYTES = 1024 * 1024
_SIZE_ERROR = "El archivo de FFmpeg supera el tamaño permitido."


def resolve_ffmpeg_location(data_dir: Path, *, audio_only: bool) -> str | None:
    """Devuelve la ruta de FFmpeg para yt-dlp (``None`` = usar el del PATH).

    Para video basta el binario empaquetado por imageio-ffmpeg (remux/convert).
    Para audio se busca en el sistema y, si no existe, se prepara una copia local.
    """
    return _ensure_local_ffmpeg(data_dir) if audio_only else imageio_ffmpeg.get_ffmpeg_exe()


def _runs_ok(executable: str | Path, timeout: float = 10) -> bool:
    try:
        subprocess.run([str(executable), "-version"], check=True, capture_output=True, timeout=timeout)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


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


def _ensure_local_ffmpeg(data_dir: Path) -> str | None:
    if _runs_ok("ffmpeg"):
        return None  # yt-dlp lo resuelve por PATH

    target_dir = data_dir / ".tools" / "ffmpeg"
    executable = target_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    target_dir.mkdir(parents=True, exist_ok=True)
    _hide_windows_directory(target_dir.parent)
    _hide_windows_directory(target_dir)

    if executable.is_file():
        if _runs_ok(executable):
            return str(executable)
        executable.unlink(missing_ok=True)

    if os.name == "nt":
        _download_windows_build(target_dir, executable)
    else:
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), executable)
        executable.chmod(executable.stat().st_mode | 0o111)

    if not _runs_ok(executable, timeout=20):
        raise RuntimeError(f"FFmpeg no quedó disponible en {executable}.")
    return str(executable)


def _download_windows_build(target_dir: Path, executable: Path) -> None:
    archive_path = target_dir / "ffmpeg-download.zip"
    temporary = target_dir / "ffmpeg-download.exe"
    try:
        asset = _latest_asset()
        checksum = _expected_sha256(asset)
        _download_archive(asset["browser_download_url"], archive_path)
        if _sha256(archive_path) != checksum:
            raise RuntimeError("La verificación SHA-256 del ZIP de FFmpeg falló.")
        _extract_ffmpeg(archive_path, temporary)
        subprocess.run([str(temporary), "-version"], check=True, capture_output=True, timeout=20)
        temporary.replace(executable)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, subprocess.SubprocessError,
            json.JSONDecodeError, StopIteration, KeyError) as exc:
        raise RuntimeError(f"No se pudo descargar o preparar FFmpeg: {exc}") from exc
    finally:
        archive_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def _latest_asset() -> dict:
    request = urllib.request.Request(
        _RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    asset = next(a for a in release.get("assets", []) if a.get("name", "").endswith(_ASSET_SUFFIX))
    if asset.get("size", 0) > _MAX_ARCHIVE_BYTES:
        raise RuntimeError(_SIZE_ERROR)
    return asset


def _expected_sha256(asset: dict) -> str:
    digest = asset.get("digest", "")
    if not digest.startswith("sha256:"):
        raise RuntimeError("GitHub no publicó un SHA-256 válido para el ZIP de FFmpeg.")
    return digest.removeprefix("sha256:").lower()


def _download_archive(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > _MAX_ARCHIVE_BYTES:
            raise RuntimeError(_SIZE_ERROR)
        received = 0
        while chunk := response.read(_CHUNK_BYTES):
            received += len(chunk)
            if received > _MAX_ARCHIVE_BYTES:
                raise RuntimeError(_SIZE_ERROR)
            output.write(chunk)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_ffmpeg(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        member = next((n for n in archive.namelist() if n.lower().endswith("/bin/ffmpeg.exe")), None)
        if member is None:
            raise RuntimeError("El ZIP descargado no contiene ffmpeg.exe.")
        with archive.open(member) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output, _CHUNK_BYTES)