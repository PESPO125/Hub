import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def plugins_dir(tmp_path: Path) -> Path:
    d = tmp_path / "plugins"
    d.mkdir()
    return d


@pytest.fixture
def client(tmp_path: Path, plugins_dir: Path):
    s = Settings(database_url=f"sqlite:///{tmp_path/'t.sqlite3'}", plugins_dir=plugins_dir, data_dir=tmp_path / "data")
    with TestClient(create_app(s)) as c:
        yield c


def write_plugin(root: Path, folder: str, manifest: dict | str) -> None:
    (root / folder).mkdir(parents=True, exist_ok=True)
    text = manifest if isinstance(manifest, str) else json.dumps(manifest)
    (root / folder / "plugin.json").write_text(text)


def good(pid: str = "demo-tool", **over) -> dict:
    m = {"id": pid, "name": "Demo", "version": "1.0.0", "integration": {"type": "subprocess"}, "categories": ["utilities"]}
    m.update(over)
    return m
