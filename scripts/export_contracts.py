"""Regenera los contratos a partir de los modelos Pydantic (fuente de verdad)."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.main import create_app  # noqa: E402
from app.modules.plugins.manifest import PluginManifest  # noqa: E402

(root / "packages/contracts/plugin-manifest.schema.json").write_text(json.dumps(PluginManifest.model_json_schema(), indent=2))
(root / "packages/contracts/api/openapi.json").write_text(json.dumps(create_app().openapi(), indent=2))
print("contracts exported")
