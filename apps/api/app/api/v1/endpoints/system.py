from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import API_VERSION, PLATFORM_VERSION, Settings
from app.modules.plugins.registry import PluginRegistry

router = APIRouter(tags=["system"])


def _storage_ok(data_dir: Path) -> bool:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


@router.get("/health")
def health() -> dict:
    """Liveness: el proceso responde."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db), s: Settings = Depends(get_app_settings)) -> dict:
    checks = {"database": False, "storage": _storage_ok(s.data_dir), "plugins_dir": s.plugins_dir.is_dir()}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    ok = checks["database"] and checks["storage"]
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "not_ready", "checks": checks}


@router.get("/app/info")
def app_info(s: Settings = Depends(get_app_settings)) -> dict:
    return {
        "name": "Hub",
        "version": PLATFORM_VERSION,
        "api_version": API_VERSION,
        "environment": s.env,
        "untrusted_plugins_allowed": s.allow_untrusted_plugins,
        "mode": "single_user_local",
    }


@router.get("/diagnostics")
def diagnostics(
    db: Session = Depends(get_db),
    s: Settings = Depends(get_app_settings),
    registry: PluginRegistry = Depends(get_registry),
) -> dict:
    counts: dict[str, int] = {"available": 0, "incompatible": 0, "invalid": 0}
    for p in registry.all():
        counts[p.status] += 1
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "database": {"ok": db_ok, "engine": s.database_url.split(":", 1)[0]},
        "storage": {"ok": _storage_ok(s.data_dir)},
        "plugins": {"directory_exists": s.plugins_dir.is_dir(), "counts": counts},
    }
