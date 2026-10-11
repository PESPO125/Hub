import json
import sys
from threading import Event, Thread
import time

from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, Settings
from app.main import create_app
from app.modules.execution.contract import RunRequest
from app.modules.execution.schema import SchemaError, validate_params
from app.modules.execution.subprocess_runner import SubprocessRunner


def test_params_schema_validates_required_fields_and_types():
    schema = {
        "type": "object",
        "required": ["url"],
        "properties": {"url": {"type": "string", "minLength": 8}},
        "additionalProperties": False,
    }
    validate_params(schema, {"url": "https://x"})
    for params in ({}, {"url": 123}, {"url": "x"}, {"url": "https://x", "extra": True}):
        try:
            validate_params(schema, params)
        except SchemaError:
            continue
        raise AssertionError(f"parameters unexpectedly accepted: {params!r}")
    try:
        validate_params({"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}},
                        {"url": "https://[invalid"})
    except SchemaError:
        pass
    else:
        raise AssertionError("malformed URI unexpectedly accepted")


def test_subprocess_runner_reports_invalid_json_and_timeout(tmp_path):
    script = tmp_path / "plugin.py"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    runner = SubprocessRunner()
    script.write_text("print('not json', flush=True)\n")
    req = RunRequest("sample-plugin", "tool", {}, tmp_path, script, work_dir, sys.executable, 3, {})
    events = list(runner.run(req, Event()))
    assert events[0]["code"] == "invalid_plugin_output"

    script.write_text("import sys, time\nsys.stdin.readline()\ntime.sleep(10)\n")
    req = RunRequest("sample-plugin", "tool", {}, tmp_path, script, work_dir, sys.executable, 1, {})
    events = list(runner.run(req, Event()))
    assert any(event.get("code") == "plugin_timeout" for event in events)

    cancel = Event()
    req = RunRequest("sample-plugin", "tool", {}, tmp_path, script, work_dir, sys.executable, 10, {})
    results = []
    worker = Thread(target=lambda: results.extend(runner.run(req, cancel)))
    worker.start()
    time.sleep(0.2)
    cancel.set()
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert any(event["type"] == "cancelled" for event in results)


def test_create_task_runs_subprocess_and_stores_outputs(tmp_path, monkeypatch):
    from app.modules.tasks import executor

    plugins = tmp_path / "plugins"
    folder = plugins / "sample-plugin"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps({
        "id": "sample-plugin",
        "name": "Sample",
        "version": "1.0",
        "integration": {"type": "subprocess", "entrypoint": "main.py"},
        "tools": [{
            "id": "create-file",
            "name": "Create file",
            "params_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string", "maxLength": 50}},
                "additionalProperties": False,
            },
            "timeout_seconds": 5,
        }],
    }))
    (folder / "main.py").write_text(
        "import json, pathlib, sys\n"
        "req = json.loads(sys.stdin.readline())\n"
        "pathlib.Path(req['work_dir'], 'result.txt').write_text(req['params']['text'])\n"
        "print(json.dumps({'type':'progress','value':0.5,'message':'Trabajando'}), flush=True)\n"
        "print(json.dumps({'type':'output','path':'result.txt','display_name':'result.txt'}), flush=True)\n"
        "print(json.dumps({'type':'done'}), flush=True)\n"
    )
    monkeypatch.setattr(executor, "_plugin_python", lambda *_args: sys.executable)
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'hub.sqlite3'}", plugins_dir=plugins,
                        data_dir=tmp_path / "data", allow_untrusted_plugins=True,
                        allowed_hosts="testserver,127.0.0.1,localhost")
    with TestClient(create_app(settings)) as client:
        client.post("/api/v1/plugins/refresh")
        client.patch("/api/v1/plugins/sample-plugin/state", json={"enabled": True})
        invalid = client.post("/api/v1/tasks", json={
            "plugin_id": "sample-plugin", "tool_id": "create-file", "params": {"other": "x"},
        })
        assert invalid.status_code == 422
        response = client.post("/api/v1/tasks", json={
            "plugin_id": "sample-plugin", "tool_id": "create-file", "params": {"text": "hello"},
        })
        assert response.status_code == 202
        assert response.json()["timeout_seconds"] == 5
        task_id = response.json()["id"]
        deadline = time.monotonic() + 5
        task = None
        while time.monotonic() < deadline:
            task = next((item for item in client.get("/api/v1/tasks").json()["items"] if item["id"] == task_id), None)
            if task and task["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)
        assert task and task["status"] == "completed", task
        files = client.get("/api/v1/files").json()["items"]
        assert len(files) == 1
        assert client.get(f"/api/v1/files/{files[0]['id']}/download").content == b"hello"


def test_builtin_youtube_subprocess_runs_when_external_plugins_are_disabled(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'hub.sqlite3'}",
                        plugins_dir=REPO_ROOT / "plugins", data_dir=tmp_path / "data",
                        allow_untrusted_plugins=False, allowed_hosts="testserver,127.0.0.1,localhost")
    with TestClient(create_app(settings)) as client:
        client.patch("/api/v1/plugins/youtube-dl/state", json={"enabled": True})
        response = client.post("/api/v1/tasks", json={
            "plugin_id": "youtube-dl", "tool_id": "download-video",
            "params": {"url": "https://example.com/video"},
        })
        assert response.status_code == 202
        task_id = response.json()["id"]
        deadline = time.monotonic() + 5
        task = None
        while time.monotonic() < deadline:
            task = next((item for item in client.get("/api/v1/tasks").json()["items"] if item["id"] == task_id), None)
            if task and task["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)
        assert task and task["status"] == "failed", task
        assert task["error"]["code"] == "invalid_video_url"


def test_task_cancellation_terminates_plugin_process(tmp_path, monkeypatch):
    from app.modules.tasks import executor

    plugins = tmp_path / "plugins"
    folder = plugins / "sleep-plugin"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps({
        "id": "sleep-plugin", "name": "Sleep", "version": "1.0",
        "integration": {"type": "subprocess", "entrypoint": "main.py"},
        "tools": [{"id": "sleep", "name": "Sleep", "timeout_seconds": 30}],
    }))
    (folder / "main.py").write_text("import sys, time\nsys.stdin.readline()\ntime.sleep(30)\n")
    monkeypatch.setattr(executor, "_plugin_python", lambda *_args: sys.executable)
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'hub.sqlite3'}", plugins_dir=plugins,
                        data_dir=tmp_path / "data", allow_untrusted_plugins=True,
                        allowed_hosts="testserver,127.0.0.1,localhost")
    with TestClient(create_app(settings)) as client:
        client.post("/api/v1/plugins/refresh")
        client.patch("/api/v1/plugins/sleep-plugin/state", json={"enabled": True})
        response = client.post("/api/v1/tasks", json={
            "plugin_id": "sleep-plugin", "tool_id": "sleep", "params": {},
        })
        task_id = response.json()["id"]
        deadline = time.monotonic() + 3
        running = False
        while time.monotonic() < deadline:
            running = any(row["id"] == task_id for row in client.get("/api/v1/tasks?status=running").json()["items"])
            if running:
                break
            time.sleep(0.05)
        assert running
        assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200
        deadline = time.monotonic() + 3
        task = None
        while time.monotonic() < deadline:
            task = next((row for row in client.get("/api/v1/tasks").json()["items"] if row["id"] == task_id), None)
            if task and task["status"] == "cancelled":
                break
            time.sleep(0.05)
        assert task and task["status"] == "cancelled", task
