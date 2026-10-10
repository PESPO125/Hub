from pathlib import Path

from app.core.config import REPO_ROOT, Settings

CORE_SUBPROCESS_PLUGINS = frozenset({"youtube-dl"})


def is_core_plugin(plugin_id: str, plugin_dir: Path, settings: Settings) -> bool:
    """Core trust is code-owned and bound to the shipped plugin directory."""
    return (
        plugin_id in CORE_SUBPROCESS_PLUGINS
        and plugin_dir.resolve() == (REPO_ROOT / "plugins" / plugin_id).resolve()
        and settings.plugins_dir.resolve() == (REPO_ROOT / "plugins").resolve()
    )
