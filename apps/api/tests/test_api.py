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


def test_rejects_unknown_host(client):
    assert client.get("/api/v1/health", headers={"host": "evil.example"}).status_code == 400


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


def test_youtube_downloader_settings_validate_and_persist(client, tmp_path):
    from pathlib import Path

    endpoint = "/api/v1/plugins/youtube-dl/config"
    defaults = client.get(endpoint).json()
    assert defaults["output_format"] == "mp4"
    assert defaults["quality"] == "best"
    assert Path(defaults["output_directory"]).name == "downloads"

    settings = {
        "output_directory": str(tmp_path / "video exports"),
        "output_format": "wav",
        "quality": "1080",
    }
    response = client.put(endpoint, json=settings)
    assert response.status_code == 200
    assert client.get(endpoint).json() == settings
    assert Path(settings["output_directory"]).is_dir()
    assert client.put(endpoint, json={**settings, "output_format": "avi"}).status_code == 422


def test_output_directory_must_be_allowed(client, monkeypatch, tmp_path):
    from pathlib import Path

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    endpoint = "/api/v1/plugins/youtube-dl/config"
    ok = {"output_directory": str(tmp_path / "ok"), "output_format": "mp4", "quality": "best"}
    assert client.put(endpoint, json=ok).status_code == 200
    forbidden = "/etc" if Path("/etc").exists() else "C:/Windows"
    response = client.put(endpoint, json={**ok, "output_directory": forbidden})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "output_directory_not_allowed"


def test_youtube_download_validates_plugin_and_returns_video(client, plugins_dir, monkeypatch, tmp_path):
    from pathlib import Path

    from app.api.v1.endpoints import youtube_dl

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    endpoint = "/api/v1/plugins/youtube-dl/download"
    assert client.post(endpoint, json={"url": "https://example.com/video"}).status_code == 422
    assert client.post(endpoint, json={"url": "https://[invalid"}).status_code == 422
    assert client.post(endpoint, json={"url": "https://youtu.be/video"}).status_code == 409
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})
    output_dir = tmp_path / "preferred-download-folder"
    output_dir.mkdir()
    (output_dir / "video123.mp4").write_bytes(b"previous video")
    client.put("/api/v1/plugins/youtube-dl/config", json={
        "output_directory": str(output_dir), "output_format": "mp4", "quality": "1080",
    })

    def fake_youtube_dl(options):
        class FakeYoutubeDL:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def extract_info(self, _url, download):
                assert download is True
                assert options["format"] == "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[ext=mp4]"
                assert options["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
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
    assert "video123%20%281%29.mp4" in response.headers["content-disposition"]

    task_page = client.get("/api/v1/tasks").json()
    assert task_page["total"] == 1
    assert task_page["items"][0]["plugin_id"] == "youtube-dl"
    assert task_page["items"][0]["operation"] == "download-video"
    assert task_page["items"][0]["status"] == "completed"

    file_page = client.get("/api/v1/files").json()
    assert file_page["total"] == 1
    stored_file = file_page["items"][0]
    assert stored_file["task_id"] == task_page["items"][0]["id"]
    assert stored_file["display_name"] == "video123 (1).mp4"
    assert stored_file["size_bytes"] == len(b"video-data")
    stored_response = client.get(f"/api/v1/files/{stored_file['id']}/download")
    assert stored_response.content == b"video-data"
    assert (output_dir / "video123 (1).mp4").read_bytes() == b"video-data"


def test_youtube_download_applies_audio_format(client, plugins_dir, monkeypatch, tmp_path):
    from pathlib import Path

    from app.api.v1.endpoints import youtube_dl

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})
    output_dir = tmp_path / "exported"
    client.put("/api/v1/plugins/youtube-dl/config", json={
        "output_directory": str(output_dir),
        "output_format": "mp3",
        "quality": "1080",
    })

    class AudioYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, download):
            assert download is True
            assert self.options["format"] == "bestaudio/best"
            assert self.options["postprocessors"] == [{
                "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320",
            }]
            self.options["progress_hooks"][0]({
                "status": "downloading", "downloaded_bytes": 500_000, "total_bytes": 1_000_000,
                "speed": 2_000_000,
            })
            running = client.get("/api/v1/tasks?status=running").json()["items"][0]
            assert running["progress"] == 0.5
            assert "2.00 MB/s" in running["message"]
            audio_path = Path(self.options["outtmpl"].replace("%(id)s", "audio123").replace("%(ext)s", "mp3"))
            audio_path.write_bytes(b"audio-data")
            return {"id": "audio123", "ext": "mp3", "filepath": str(audio_path)}

    monkeypatch.setattr(youtube_dl.yt_dlp, "YoutubeDL", AudioYoutubeDL)
    response = client.post("/api/v1/plugins/youtube-dl/download", json={
        "url": "https://youtu.be/audio",
        "save_to_output_directory": False,
    })
    assert response.status_code == 200
    assert "audio123.mp3" in response.headers["content-disposition"]
    assert response.content == b"audio-data"
    assert not (output_dir / "audio123.mp3").exists()
    assert client.get("/api/v1/files").json()["total"] == 1


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
    task = client.get("/api/v1/tasks").json()["items"][0]
    assert task["status"] == "failed"
    assert task["error"]["code"] == "download_failed"
    assert client.get("/api/v1/files").json()["total"] == 0


def test_youtube_download_reports_sanitized_unexpected_error(client, plugins_dir, monkeypatch):
    from app.api.v1.endpoints import youtube_dl

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})

    class BrokenYoutubeDL:
        def __init__(self, _options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, url, download):
            assert download is True
            raise RuntimeError(f"conversion failed for {url}")

    monkeypatch.setattr(youtube_dl.yt_dlp, "YoutubeDL", BrokenYoutubeDL)
    url = "https://youtu.be/private-video"
    response = client.post("/api/v1/plugins/youtube-dl/download", json={"url": url})
    message = response.json()["error"]["message"]
    assert response.status_code == 500
    assert "RuntimeError: conversion failed" in message
    assert url not in message


def test_youtube_download_cancellation_stops_running_task(client, plugins_dir, monkeypatch):
    from app.api.v1.endpoints import youtube_dl
    from tempfile import TemporaryDirectory

    write_plugin(plugins_dir, "youtube-dl", good("youtube-dl"))
    client.post("/api/v1/plugins/refresh")
    client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})

    def create_temporary_directory(*, prefix, dir, ignore_cleanup_errors=False):
        assert ignore_cleanup_errors is True
        return TemporaryDirectory(prefix=prefix, dir=dir, ignore_cleanup_errors=ignore_cleanup_errors)

    monkeypatch.setattr(youtube_dl.tempfile, "TemporaryDirectory", create_temporary_directory)

    class CancelledYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, download):
            assert download is True
            task = client.get("/api/v1/tasks").json()["items"][0]
            second_download = client.post(
                "/api/v1/plugins/youtube-dl/download",
                json={"url": "https://youtu.be/second-video"},
            )
            assert second_download.status_code == 409
            assert second_download.json()["error"]["code"] == "download_in_progress"
            cancel_response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
            assert cancel_response.status_code == 200
            self.options["progress_hooks"][0](
                {"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100}
            )
            raise AssertionError("progress hook should stop the download")

    monkeypatch.setattr(youtube_dl.yt_dlp, "YoutubeDL", CancelledYoutubeDL)
    response = client.post("/api/v1/plugins/youtube-dl/download", json={"url": "https://youtu.be/video"})
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "La descarga fue cancelada."
    task = client.get("/api/v1/tasks").json()["items"][0]
    assert task["status"] == "cancelled"
    assert task["progress"] == 0.25
    assert client.get("/api/v1/files").json()["total"] == 0


def test_relative_paths_anchor_to_repo_root(monkeypatch, tmp_path):
    from app.core.config import REPO_ROOT, Settings
    monkeypatch.chdir(tmp_path)  # el cwd no debe influir
    s = Settings()
    assert s.plugins_dir == (REPO_ROOT / "plugins").resolve()
    assert s.database_url == f"sqlite:///{(REPO_ROOT / 'data' / 'hub.sqlite3').resolve()}"
