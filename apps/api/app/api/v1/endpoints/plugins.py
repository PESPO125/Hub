from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import Preference
from app.modules.plugins import service
from app.modules.plugins.registry import PluginRegistry

router = APIRouter(tags=["plugins"])


class StateBody(BaseModel):
    enabled: bool


def _views(db, registry, s):
    states, favs = service.admin_states(db), service.get_favorites(db)
    return [service.to_view(p, states, favs, s) for p in registry.all()]


@router.get("/plugins")
def list_plugins(
    status: Literal["available", "incompatible", "invalid"] | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    s: Settings = Depends(get_app_settings),
) -> dict:
    items = [v for v in _views(db, registry, s) if status is None or v["status"] == status]
    return {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset}


@router.post("/plugins/refresh")
def refresh(
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    s: Settings = Depends(get_app_settings),
) -> dict:
    """Re-escanea la carpeta de plugins. No ejecuta código de plugins."""
    registry.refresh()
    service.audit(db, "plugins.refresh")
    db.commit()
    views = _views(db, registry, s)
    return {"total": len(views), "items": views}


@router.get("/plugins/{plugin_id}")
def get_plugin(
    plugin_id: str,
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    s: Settings = Depends(get_app_settings),
) -> dict:
    plugin = registry.get(plugin_id)
    if plugin is None:
        raise AppError(404, "plugin_not_found", "Plugin no encontrado.")
    return service.to_view(plugin, service.admin_states(db), service.get_favorites(db), s)


@router.patch("/plugins/{plugin_id}/state")
def set_state(
    plugin_id: str,
    body: StateBody,
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    s: Settings = Depends(get_app_settings),
) -> dict:
    service.set_admin_state(db, registry, plugin_id, body.enabled)
    return get_plugin(plugin_id, db, registry, s)


@router.put("/favorites/{plugin_id}")
def add_favorite(plugin_id: str, db: Session = Depends(get_db), registry: PluginRegistry = Depends(get_registry)) -> dict:
    if registry.get(plugin_id) is None:
        raise AppError(404, "plugin_not_found", "Plugin no encontrado.")
    favs = service.get_favorites(db)
    if plugin_id not in favs:
        favs.append(plugin_id)
    db.merge(Preference(key="favorites", value=favs))
    db.commit()
    return {"favorites": favs}


@router.delete("/favorites/{plugin_id}")
def remove_favorite(plugin_id: str, db: Session = Depends(get_db)) -> dict:
    favs = [f for f in service.get_favorites(db) if f != plugin_id]
    db.merge(Preference(key="favorites", value=favs))
    db.commit()
    return {"favorites": favs}


@router.get("/catalog")
def catalog(
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=30),
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
    s: Settings = Depends(get_app_settings),
) -> dict:
    """Catálogo: plugins válidos (disponibles o incompatibles). Los inválidos solo aparecen en administración."""
    base = [v for v in _views(db, registry, s) if v["status"] in ("available", "incompatible")]
    cats = sorted({c for v in base for c in v["categories"]})
    items = base
    if q:
        ql = q.lower()
        items = [v for v in items if ql in v["name"].lower() or ql in v["description"].lower()
                 or any(ql in t["name"].lower() for t in v["tools"])]
    if category:
        items = [v for v in items if category in v["categories"]]
    if favorites_only:
        items = [v for v in items if v["favorite"]]
    return {"items": items, "total": len(items), "categories": cats, "installed_total": len(base)}
