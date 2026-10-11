from tests.conftest import good, write_plugin


def test_health_ready_info(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    response = client.get("/api/v1/ready")
    assert response.status_code == 200 and response.json()["checks"]["database"] is True
    assert client.get("/api/v1/app/info").json()["untrusted_plugins_allowed"] is False


def test_starts_empty_and_catalog_empty(client):
    assert client.get("/api/v1/plugins").json()["total"] == 0
    catalog = client.get("/api/v1/catalog").json()
    assert catalog["items"] == [] and catalog["installed_total"] == 0
    assert client.get("/api/v1/tasks").json()["total"] == 0
    assert client.get("/api/v1/files").json()["total"] == 0


def test_error_format_and_request_id(client):
    response = client.get("/api/v1/plugins/nope")
    assert response.status_code == 404 and response.json()["error"]["code"] == "plugin_not_found"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert client.get("/api/v1/tasks?limit=0").status_code == 422


def test_rejects_unknown_host(client):
    response = client.get("/api/v1/health", headers={"host": "evil.example"})
    assert response.status_code == 400


def test_settings_roundtrip(client):
    assert client.get("/api/v1/settings").json()["theme"] == "system"
    assert client.put("/api/v1/settings", json={"theme": "dark"}).json()["theme"] == "dark"
    assert client.put("/api/v1/settings", json={"theme": "neon"}).status_code == 422


def test_enable_disable_and_favorites(client, plugins_dir):
    write_plugin(plugins_dir, "a", good("alpha-tool"))
    client.post("/api/v1/plugins/refresh")
    plugin = client.get("/api/v1/plugins/alpha-tool").json()
    assert plugin["status"] == "available" and plugin["enabled"] is False
    plugin = client.patch("/api/v1/plugins/alpha-tool/state", json={"enabled": True}).json()
    assert plugin["enabled"] is True and plugin["executable"] is False
    assert "no confiables" in plugin["executable_reason"]
    assert client.put("/api/v1/favorites/alpha-tool").json()["favorites"] == ["alpha-tool"]
    assert client.get("/api/v1/catalog?favorites_only=true").json()["total"] == 1
    assert client.get("/api/v1/catalog?q=zzz").json()["total"] == 0


def test_cannot_enable_invalid_or_incompatible(client, plugins_dir):
    write_plugin(plugins_dir, "bad", "{not json")
    write_plugin(plugins_dir, "old", good("old-tool", contract_version=99))
    client.post("/api/v1/plugins/refresh")
    assert client.patch("/api/v1/plugins/old-tool/state", json={"enabled": True}).status_code == 409
    assert client.patch("/api/v1/plugins/invalid:bad/state", json={"enabled": True}).status_code == 409
    catalog = client.get("/api/v1/catalog").json()
    assert [item["id"] for item in catalog["items"]] == ["old-tool"]


def test_cancel_unknown_task(client):
    assert client.post("/api/v1/tasks/x/cancel").status_code == 404


def test_plugin_config_roundtrip(client, plugins_dir):
    write_plugin(plugins_dir, "config-tool", good("config-tool"))
    client.post("/api/v1/plugins/refresh")
    endpoint = "/api/v1/plugins/config-tool/config"
    config = {"format": "mp4", "quality": "best"}
    assert client.get(endpoint).json() == {}
    assert client.put(endpoint, json=config).json() == config
    assert client.get(endpoint).json() == config
    assert client.get("/api/v1/plugins/missing-tool/config").status_code == 404


def test_relative_paths_anchor_to_repo_root(monkeypatch, tmp_path):
    from app.core.config import REPO_ROOT, Settings

    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.plugins_dir == (REPO_ROOT / "plugins").resolve()
    assert settings.database_url == f"sqlite:///{(REPO_ROOT / 'data' / 'hub.sqlite3').resolve()}"
