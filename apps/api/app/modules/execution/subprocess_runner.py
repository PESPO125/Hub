from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.modules.execution.contract import PluginRunner, RunRequest

log = logging.getLogger(__name__)
MAX_EVENT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024


class SubprocessRunner(PluginRunner):
    """JSON-lines subprocess adapter. The plugin process never inherits Hub's environment."""

    def run(self, req: RunRequest, cancel: threading.Event) -> Iterator[dict[str, Any]]:
        env = _minimal_env(req.work_dir)
        flags: dict[str, Any] = {}
        if os.name == "nt":
            flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            flags["start_new_session"] = True
        try:
            process = subprocess.Popen(
                [req.python, str(req.entrypoint)], cwd=req.work_dir, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                **flags,
            )
        except OSError as exc:
            yield {"type": "error", "code": "plugin_start_failed", "message": f"No se pudo iniciar el plugin ({type(exc).__name__})."}
            return

        stderr_thread = threading.Thread(target=_drain_stderr, args=(process.stderr, req.plugin_id), daemon=True)
        stderr_thread.start()
        timed_out = threading.Event()
        monitor = threading.Thread(target=_watch_process,
                                   args=(process, cancel, timed_out, req.timeout_seconds), daemon=True)
        monitor.start()
        try:
            payload = (json.dumps(req.payload, ensure_ascii=False) + "\n").encode("utf-8")
            if len(payload) > MAX_EVENT_BYTES:
                _terminate_tree(process)
                yield {"type": "error", "code": "request_too_large", "message": "Los parámetros superan el límite permitido."}
                return
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(payload)
            process.stdin.close()
            bytes_read = 0
            saw_done = False
            while True:
                line = process.stdout.readline(MAX_EVENT_BYTES + 1)
                if not line:
                    break
                bytes_read += len(line)
                if len(line) > MAX_EVENT_BYTES or bytes_read > MAX_OUTPUT_BYTES:
                    _terminate_tree(process)
                    yield {"type": "error", "code": "plugin_output_limit", "message": "El plugin superó el límite de salida."}
                    return
                try:
                    event = _parse_event(line)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    _terminate_tree(process)
                    yield {"type": "error", "code": "invalid_plugin_output", "message": f"El plugin emitió un evento inválido ({type(exc).__name__})."}
                    return
                if saw_done:
                    _terminate_tree(process)
                    yield {"type": "error", "code": "invalid_plugin_output", "message": "El plugin emitió datos después del evento final."}
                    return
                yield event
                saw_done = event["type"] == "done"
                if event["type"] == "error":
                    break
            return_code = process.wait(timeout=req.timeout_seconds + 2)
            if cancel.is_set():
                yield {"type": "cancelled"}
            elif timed_out.is_set():
                yield {"type": "error", "code": "plugin_timeout", "message": "El plugin superó el tiempo máximo de ejecución."}
            elif return_code != 0:
                yield {"type": "error", "code": "plugin_crashed", "message": f"El plugin terminó con código {return_code}."}
        finally:
            if process.poll() is None:
                _terminate_tree(process)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            if process.stderr:
                process.stderr.close()
            stderr_thread.join(timeout=1)


def _minimal_env(work_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "HOME": str(work_dir), "PYTHONIOENCODING": "utf-8",
    }
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def _parse_event(line: bytes) -> dict[str, Any]:
    event = json.loads(line.decode("utf-8"))
    if not isinstance(event, dict) or event.get("type") not in {"progress", "output", "error", "done"}:
        raise ValueError("unknown event")
    kind = event["type"]
    if kind == "progress":
        value = event.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError("invalid progress")
        message = event.get("message", "")
        if not isinstance(message, str):
            raise ValueError("invalid progress message")
        return {"type": kind, "value": float(value), "message": message[:500]}
    if kind == "output":
        path, name = event.get("path"), event.get("display_name")
        if not isinstance(path, str) or not path or not isinstance(name, str) or not name:
            raise ValueError("invalid output")
        return {"type": kind, "path": path[:1024], "display_name": name[:255]}
    if kind == "error":
        code, message = event.get("code"), event.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            raise ValueError("invalid error")
        return {"type": kind, "code": code[:64], "message": message[:500]}
    return {"type": kind}


def _drain_stderr(stream, plugin_id: str) -> None:
    total = 0
    try:
        for line in iter(stream.readline, b""):
            total += len(line)
            if total <= MAX_STDERR_BYTES:
                log.info("plugin %s stderr: %s", plugin_id, line[:4096].decode("utf-8", "replace").rstrip())
    except (OSError, ValueError):
        pass


def _watch_process(process: subprocess.Popen, cancel: threading.Event, timed_out: threading.Event, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while process.poll() is None:
        if cancel.wait(0.1):
            _terminate_tree(process)
            return
        if time.monotonic() >= deadline:
            timed_out.set()
            _terminate_tree(process)
            return


def _terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        process.kill()
