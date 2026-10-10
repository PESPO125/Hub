"""Descubrimiento y registro. NUNCA importa ni ejecuta código del plugin."""
import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.core.config import PLATFORM_VERSION
from app.modules.plugins.manifest import CONTRACT_VERSIONS_SUPPORTED, PluginManifest

MANIFEST_NAME = "plugin.json"
MAX_MANIFEST_BYTES = 64 * 1024


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


@dataclass
class DiscoveredPlugin:
    folder: str
    status: str  # available | incompatible | invalid
    manifest: PluginManifest | None = None
    manifest_hash: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.manifest.id if self.manifest else f"invalid:{self.folder}"


def _read_manifest(folder: Path, root: Path) -> tuple[bytes | None, str | None]:
    try:
        resolved = (folder / MANIFEST_NAME).resolve(strict=True)
    except OSError:
        return None, "No se encontró plugin.json."
    if not resolved.is_relative_to(root):  # traversal / symlink que escapa
        return None, "El manifiesto apunta fuera del directorio de plugins."
    if not resolved.is_file():
        return None, "plugin.json no es un archivo regular."
    if resolved.stat().st_size > MAX_MANIFEST_BYTES:
        return None, "plugin.json supera el tamaño máximo permitido."
    return resolved.read_bytes(), None


def scan_directory(plugins_dir: Path) -> list[DiscoveredPlugin]:
    root = plugins_dir.resolve()
    if not root.is_dir():
        return []
    found: list[DiscoveredPlugin] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        try:
            if not entry.resolve().is_relative_to(root):
                found.append(DiscoveredPlugin(entry.name, "invalid", problems=["La carpeta apunta fuera del directorio de plugins."]))
                continue
            raw, err = _read_manifest(entry, root)
            if err or raw is None:
                found.append(DiscoveredPlugin(entry.name, "invalid", problems=[err or "Manifiesto ilegible."]))
                continue
            digest = hashlib.sha256(raw).hexdigest()
            try:
                manifest = PluginManifest.model_validate(json.loads(raw))
            except (json.JSONDecodeError, UnicodeDecodeError):
                found.append(DiscoveredPlugin(entry.name, "invalid", manifest_hash=digest, problems=["plugin.json no es JSON válido."]))
                continue
            except ValidationError as exc:
                probs = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
                found.append(DiscoveredPlugin(entry.name, "invalid", manifest_hash=digest, problems=probs))
                continue
            if manifest.integration.entrypoint:
                plugin_root = entry.resolve()
                candidate = Path(manifest.integration.entrypoint)
                if candidate.is_absolute():
                    found.append(DiscoveredPlugin(entry.name, "invalid", manifest, digest,
                                                  ["El entrypoint debe ser una ruta relativa."]))
                    continue
                try:
                    resolved = (plugin_root / candidate).resolve(strict=True)
                    if not resolved.is_relative_to(plugin_root) or not resolved.is_file():
                        raise OSError("outside plugin folder")
                except OSError:
                    found.append(DiscoveredPlugin(entry.name, "invalid", manifest, digest,
                                                  ["El entrypoint no existe o apunta fuera del plugin."]))
                    continue
            found.append(_check_compat(entry.name, manifest, digest))
        except Exception as exc:  # un plugin roto jamás tumba el escaneo
            found.append(DiscoveredPlugin(entry.name, "invalid", problems=[f"Error al leer el plugin: {type(exc).__name__}"]))
    return _mark_duplicates(found)


def _check_compat(folder: str, m: PluginManifest, digest: str) -> DiscoveredPlugin:
    problems: list[str] = []
    if m.contract_version not in CONTRACT_VERSIONS_SUPPORTED:
        problems.append(f"Contrato v{m.contract_version} no soportado (soportados: {list(CONTRACT_VERSIONS_SUPPORTED)}).")
    cur = _ver(PLATFORM_VERSION)
    if _ver(m.platform.min_version) > cur:
        problems.append(f"Requiere plataforma >= {m.platform.min_version} (actual {PLATFORM_VERSION}).")
    if m.platform.max_version and _ver(m.platform.max_version) < cur:
        problems.append(f"Soporta plataforma <= {m.platform.max_version} (actual {PLATFORM_VERSION}).")
    return DiscoveredPlugin(folder, "incompatible" if problems else "available", m, digest, problems)


def _mark_duplicates(items: list[DiscoveredPlugin]) -> list[DiscoveredPlugin]:
    counts: dict[str, int] = {}
    for p in items:
        if p.manifest:
            counts[p.manifest.id] = counts.get(p.manifest.id, 0) + 1
    out = []
    for p in items:
        if p.manifest and counts[p.manifest.id] > 1:
            out.append(DiscoveredPlugin(p.folder, "invalid", None, p.manifest_hash,
                                        [f"Identificador duplicado: '{p.manifest.id}' (carpeta '{p.folder}')."]))
        else:
            out.append(p)
    return out


class PluginRegistry:
    """Snapshot reemplazado atómicamente bajo lock."""

    def __init__(self, plugins_dir: Path):
        self._dir = plugins_dir
        self._lock = threading.Lock()
        self._snapshot: list[DiscoveredPlugin] = []

    def refresh(self) -> list[DiscoveredPlugin]:
        with self._lock:
            self._snapshot = scan_directory(self._dir)
            return list(self._snapshot)

    def all(self) -> list[DiscoveredPlugin]:
        return list(self._snapshot)

    def get(self, plugin_id: str) -> DiscoveredPlugin | None:
        return next((p for p in self._snapshot if p.id == plugin_id), None)
