from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import AuditEvent, PluginRecord, Preference
from app.modules.plugins.registry import DiscoveredPlugin, PluginRegistry


def get_favorites(db: Session) -> list[str]:
    pref = db.get(Preference, "favorites")
    return list(pref.value) if pref and isinstance(pref.value, list) else []


def audit(db: Session, action: str, target: str | None = None, detail: dict | None = None) -> None:
    db.add(AuditEvent(action=action, target=target, detail=detail))


def admin_states(db: Session) -> dict[str, str]:
    return {r.id: r.admin_state for r in db.query(PluginRecord).all()}


def to_view(p: DiscoveredPlugin, states: dict[str, str], favorites: list[str], settings: Settings) -> dict:
    admin = states.get(p.id, "disabled")
    enabled = admin == "enabled" and p.status == "available"
    if not enabled:
        reason = None
    elif not settings.allow_untrusted_plugins:
        reason = "La ejecución de plugins no confiables está deshabilitada en esta instalación."
    else:
        reason = None
    m = p.manifest
    return {
        "id": p.id,
        "folder": p.folder,
        "name": m.name if m else p.folder,
        "description": m.description if m else "",
        "version": m.version if m else None,
        "contract_version": m.contract_version if m else None,
        "categories": list(m.categories) if m else [],
        "icon": m.icon if m else "puzzle",
        "integration_type": m.integration.type if m else None,
        "tools": [t.model_dump() for t in m.tools] if m else [],
        "capabilities": m.capabilities if m else [],
        "permissions": list(m.permissions) if m else [],
        "config_requirements": m.config_requirements if m else [],
        "platform": m.platform.model_dump() if m else None,
        "status": p.status,
        "admin_state": admin,
        "enabled": enabled,
        "executable": enabled and settings.allow_untrusted_plugins,
        "executable_reason": reason,
        "problems": p.problems,
        "favorite": p.id in favorites,
    }


def set_admin_state(db: Session, registry: PluginRegistry, plugin_id: str, enabled: bool) -> None:
    plugin = registry.get(plugin_id)
    if plugin is None:
        raise AppError(404, "plugin_not_found", "Plugin no encontrado.")
    if enabled and plugin.status != "available":
        raise AppError(409, "plugin_not_available", "Solo se pueden habilitar plugins válidos y compatibles.")
    rec = db.get(PluginRecord, plugin_id) or PluginRecord(id=plugin_id)
    rec.admin_state = "enabled" if enabled else "disabled"
    rec.manifest_hash = plugin.manifest_hash
    db.merge(rec)
    audit(db, "plugin.enabled" if enabled else "plugin.disabled", plugin_id)
    db.commit()
