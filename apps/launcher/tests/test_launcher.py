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
        '{"id":"qr-test","name":"QR","version":"1.0.0","integration":{"type":"subprocess"},'
        '"tools":[{"id":"gen","name":"Generar QR","description":"Crea un código"}]}')
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
    from tkinter import ttk
    monkeypatch.setattr(hl, "API_URL", "http://127.0.0.1:9")  # backend caído
    try:
        app = hl.LauncherApp()
    except tk.TclError:
        pytest.skip("sin pantalla disponible")

    def texts():
        return [w.cget("text") for w in app.inner.winfo_children() if isinstance(w, ttk.Label)]

    try:
        _pump(app)
        assert "No se pudo conectar con Hub" in texts()
        assert "Sin conexión" in app.status.cget("text")

        monkeypatch.setattr(hl, "API_URL", live_api)  # backend arriba, plugin sin habilitar
        app.refresh()
        _pump(app)
        assert "No hay herramientas habilitadas" in texts()

        import json
        import urllib.request
        req = urllib.request.Request(f"{live_api}/api/v1/plugins/qr-test/state", method="PATCH",
                                     data=json.dumps({"enabled": True}).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req).read()
        app.refresh()
        _pump(app)
        shown = [w for row in app.inner.winfo_children() for w in row.winfo_children() if isinstance(w, ttk.Label)]
        assert any(w.cget("text") == "Generar QR" for w in shown)
        assert "1 herramienta" in app.status.cget("text")

        app.query.set("zzz")
        _pump(app, 0.3)
        assert "Sin resultados" in texts()
    finally:
        app.destroy()
