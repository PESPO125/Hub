import io
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hub_launcher as hl  # noqa: E402


def test_tools_from_catalog_only_enabled_and_available():
    def p(pid, status="available", enabled=True):
        return {"id": pid, "name": pid.upper(), "status": status, "enabled": enabled,
                "tools": [{"id": "t", "name": f"Tool {pid}", "description": "d"}]}
    cat = {"items": [p("a"), p("b", enabled=False), p("c", status="incompatible"), p("d", status="invalid")]}
    assert [t.plugin_id for t in hl.tools_from_catalog(cat)] == ["a"]


def test_filter_tools():
    tools = [hl.Tool("a", "Alpha", "t", "Generar QR", "códigos"), hl.Tool("b", "Beta", "t", "Convertir", "audio")]
    assert [t.plugin_id for t in hl.filter_tools(tools, "qr")] == ["a"]
    assert [t.plugin_id for t in hl.filter_tools(tools, "BETA")] == ["b"]
    assert hl.filter_tools(tools, "  ") == tools

def test_download_youtube_video_saves_response(tmp_path, monkeypatch):
    class Headers:
        def get_filename(self):
            return "video123.mp4"

    class Response(io.BytesIO):
        headers = Headers()

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://hub/api/v1/plugins/youtube-dl/download"
        assert request.get_method() == "POST"
        assert timeout == 1800
        return Response(b"video-data")

    monkeypatch.setattr(hl.urllib.request, "urlopen", fake_urlopen)
    result = hl.download_youtube_video("https://youtu.be/video123", "http://hub", tmp_path)
    assert result.name == "video123.mp4"
    assert result.read_bytes() == b"video-data"


def test_backend_down_raises():
    with pytest.raises(hl.BackendError):
        hl.fetch_catalog("http://127.0.0.1:9", timeout=0.5)


@pytest.fixture
def live_api(tmp_path):
    from app.core.config import Settings
    from app.main import create_app
    plugins = tmp_path / "plugins"
    (plugins / "p").mkdir(parents=True)
    (plugins / "p" / "plugin.json").write_text(
        '{"id":"qr-test","name":"QR","version":"1.0","integration":{"type":"subprocess"},'
        '"tools":[{"id":"gen","name":"Generar QR","description":"Crea un código"}]}', encoding="utf-8")
    youtube_folder = plugins / "youtube-dl"
    youtube_folder.mkdir()
    (youtube_folder / "plugin.json").write_text(
        '{"id":"youtube-dl","name":"YouTube Downloader","version":"1.0",'
        '"integration":{"type":"subprocess"},"tools":[{"id":"download-video",'
        '"name":"Descargar Video","description":"Descarga videos de YouTube"}]}',
        encoding="utf-8",
    )
    s = Settings(database_url=f"sqlite:///{tmp_path/'t.db'}", plugins_dir=plugins, data_dir=tmp_path / "d")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(s), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(timeout=5)


def test_against_real_backend(live_api):
    import json
    import urllib.request
    assert hl.tools_from_catalog(hl.fetch_catalog(live_api)) == []  # deshabilitado por defecto
    req = urllib.request.Request(f"{live_api}/api/v1/plugins/qr-test/state", method="PATCH",
                                 data=json.dumps({"enabled": True}).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req).read()
    tools = hl.tools_from_catalog(hl.fetch_catalog(live_api))
    assert [(t.plugin_id, t.name) for t in tools] == [("qr-test", "Generar QR")]


def _pump(app, seconds=1.5):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def test_gui_states(live_api, monkeypatch):
    tk = pytest.importorskip("tkinter")
    monkeypatch.setattr(hl, "API_URL", live_api)
    try:
        app = hl.LauncherApp()
    except tk.TclError:
        pytest.skip("sin pantalla disponible")

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    try:
        _pump(app)
        import json
        import urllib.request

        req = urllib.request.Request(
            f"{live_api}/api/v1/plugins/youtube-dl/state",
            method="PATCH",
            data=json.dumps({"enabled": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req).read()
        app.refresh()
        _pump(app)
        youtube_tool = next(t for t in app._tools if t.plugin_id == "youtube-dl")
        launch_button = next(
            widget for widget in descendants(app.inner)
            if isinstance(widget, hl.RoundedButton) and widget.text == "Iniciar"
        )
        launch_button.command()
        assert app.search_frame.winfo_manager() == ""
        assert any(isinstance(w, tk.Entry) for w in descendants(app.inner))
        assert app._active_tool == youtube_tool
        assert app._tool_url is not None
        monkeypatch.setattr(hl, "download_youtube_video", lambda _url: Path("video.mp4"))
        app._tool_url.set("https://youtu.be/example")
        app._download_tool()
        assert app._download_status_label is not None
        assert app._download_status_label.cget("fg") == "#22c55e"
        app._close_tool()
        assert app.search_frame.winfo_manager() == "pack"
    finally:
        app.destroy()
