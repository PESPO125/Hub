from tests.conftest import good, write_plugin


def test_health_ready_info(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    r = client.get("/api/v1/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] is True
    assert client.get("/api/v1/app/info").json()["untrusted_plugins_allowed"] is False


def test_starts_empty_and_catalog_empty(client):
    assert client.get("/api/v1/plugins").json()["total"] == 0
    cat = client.get("/api/v1/catalog").json()
    assert cat["items"] == [] and cat["installed_total"] == 0
    assert client.get("/api/v1/tasks").json()["total"] == 0
    assert client.get("/api/v1/files").json()["total"] == 0


def test_error_format_and_request_id(client):
    r = client.get("/api/v1/plugins/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "plugin_not_found"
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]
    assert client.get("/api/v1/tasks?limit=0").status_code == 422


def test_settings_roundtrip(client):
    assert client.get("/api/v1/settings").json()["theme"] == "system"
    assert client.put("/api/v1/settings", json={"theme": "dark"}).json()["theme"] == "dark"
    assert client.put("/api/v1/settings", json={"theme": "neon"}).status_code == 422


def test_enable_disable_and_favorites(client, plugins_dir):
    write_plugin(plugins_dir, "a", good("alpha-tool"))
    client.post("/api/v1/plugins/refresh")
    p = client.get("/api/v1/plugins/alpha-tool").json()
    assert p["status"] == "available" and p["enabled"] is False
    p = client.patch("/api/v1/plugins/alpha-tool/state", json={"enabled": True}).json()
    assert p["enabled"] is True and p["executable"] is False  # untrusted desactivado por defecto
    assert "no confiables" in p["executable_reason"]
    assert client.put("/api/v1/favorites/alpha-tool").json()["favorites"] == ["alpha-tool"]
    assert client.get("/api/v1/catalog?favorites_only=true").json()["total"] == 1
    assert client.get("/api/v1/catalog?q=zzz").json()["total"] == 0


def test_cannot_enable_invalid_or_incompatible(client, plugins_dir):
    write_plugin(plugins_dir, "bad", "{not json")
    write_plugin(plugins_dir, "old", good("old-tool", contract_version=99))
    client.post("/api/v1/plugins/refresh")
    assert client.patch("/api/v1/plugins/old-tool/state", json={"enabled": True}).status_code == 409
    assert client.patch("/api/v1/plugins/invalid:bad/state", json={"enabled": True}).status_code == 409
    cat = client.get("/api/v1/catalog").json()
    assert [i["id"] for i in cat["items"]] == ["old-tool"]  # inválidos fuera del catálogo


def test_cancel_unknown_task(client):
    assert client.post("/api/v1/tasks/x/cancel").status_code == 404


def test_youtube_download_validates_plugin_and_returns_video(client, plugins_dir, monkeypatch):
    from pathlib import Path

    from app.api.v1.endpoints import youtube_dl

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    endpoint = "/api/v1/plugins/youtube-dl/download"
    assert client.post(endpoint, json={"url": "https://example.com/video"}).status_code == 422
    assert client.post(endpoint, json={"url": "https://[invalid"}).status_code == 422
    assert client.post(endpoint, json={"url": "https://youtu.be/video"}).status_code == 409
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})

    def fake_youtube_dl(options):
        class FakeYoutubeDL:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def extract_info(self, _url, download):
                assert download is True
                assert "format" not in options
                assert "max_downloads" not in options
                assert Path(options["ffmpeg_location"]).is_file()
                return {"id": "video123", "ext": "mp4"}

            def prepare_filename(self, info):
                filename = options["outtmpl"].replace("%(id)s", info["id"]).replace("%(ext)s", info["ext"])
                Path(filename).write_bytes(b"video-data")
                return filename

        return FakeYoutubeDL()

    monkeypatch.setattr(youtube_dl.yt_dlp, "YoutubeDL", fake_youtube_dl)
    response = client.post(endpoint, json={"url": "https://youtu.be/video"})
    assert response.status_code == 200
    assert response.content == b"video-data"
    assert "video123.mp4" in response.headers["content-disposition"]


def test_youtube_download_reports_sanitized_yt_dlp_error(client, plugins_dir, monkeypatch):
    from app.api.v1.endpoints import youtube_dl

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})

    class FailedYoutubeDL:
        def __init__(self, _options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, url, download):
            assert download is True
            raise youtube_dl.yt_dlp.utils.DownloadError(f"Video unavailable: {url}")

    monkeypatch.setattr(youtube_dl.yt_dlp, "YoutubeDL", FailedYoutubeDL)
    url = "https://youtu.be/private-video"
    response = client.post("/api/v1/plugins/youtube-dl/download", json={"url": url})
    assert response.status_code == 422
    assert "Video unavailable" in response.json()["error"]["message"]
    assert url not in response.json()["error"]["message"]


def test_relative_paths_anchor_to_repo_root(monkeypatch, tmp_path):
    from app.core.config import REPO_ROOT, Settings
    monkeypatch.chdir(tmp_path)  # el cwd no debe influir
    s = Settings()
    assert s.plugins_dir == (REPO_ROOT / "plugins").resolve()
    assert s.database_url == f"sqlite:///{(REPO_ROOT / 'data' / 'hub.sqlite3').resolve()}"
