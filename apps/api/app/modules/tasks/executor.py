from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import PluginRecord, Preference, Task, utcnow
from app.modules.execution.contract import PluginRunner, RunRequest
from app.modules.execution.schema import SchemaError, validate_params
from app.modules.execution.subprocess_runner import SubprocessRunner
from app.modules.files.storage import FileStorage, LocalFileStorage
from app.modules.plugins.registry import PluginRegistry
from app.modules.plugins.trust import is_core_plugin

log = logging.getLogger(__name__)
MAX_OUTPUT_FILES = 100
MAX_OUTPUT_FILE_BYTES = 1024**3
MAX_OUTPUT_TOTAL_BYTES = 2 * 1024**3
PROGRESS_WRITE_INTERVAL = 0.5
SUPPORTED_RUNNERS = frozenset({"subprocess"})


class TaskExecutor:
    def __init__(self, sessions: sessionmaker[Session], registry: PluginRegistry, settings: Settings):
        self.sessions = sessions
        self.registry = registry
        self.settings = settings
        self.storage: FileStorage = LocalFileStorage(settings.data_dir / "files")
        self.runners: dict[str, PluginRunner] = {"subprocess": SubprocessRunner()}
        self.pool = ThreadPoolExecutor(max_workers=settings.task_workers, thread_name_prefix="hub-task")
        self._lock = threading.RLock()
        self._futures: dict[str, Future] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._tool_locks: dict[tuple[str, str], threading.BoundedSemaphore] = {}
        self._stopped = False

    def resume_pending(self) -> None:
        with self.sessions() as db:
            ids = db.scalars(select(Task.id).where(Task.status == "pending")).all()
        for task_id in ids:
            self.enqueue(task_id)

    def enqueue(self, task_id: str) -> None:
        with self._lock:
            if self._stopped:
                raise RuntimeError("TaskExecutor is shut down")
            cancel = self._cancel.setdefault(task_id, threading.Event())
            future = self.pool.submit(self._execute, task_id, cancel)
            self._futures[task_id] = future
            future.add_done_callback(lambda _future, tid=task_id: self._forget(tid))

    def cancel(self, task_id: str) -> None:
        with self._lock:
            event = self._cancel.get(task_id)
            future = self._futures.get(task_id)
        if event:
            event.set()
        if future:
            future.cancel()

    def shutdown(self) -> None:
        with self._lock:
            self._stopped = True
            events = list(self._cancel.values())
        for event in events:
            event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    def _forget(self, task_id: str) -> None:
        with self._lock:
            self._futures.pop(task_id, None)
            self._cancel.pop(task_id, None)

    def _execute(self, task_id: str, cancel: threading.Event) -> None:
        with self.sessions() as db:
            task = db.get(Task, task_id)
            if task is None or task.status != "pending":
                return
            manifest_plugin = self.registry.get(task.plugin_id)
            if manifest_plugin is None or manifest_plugin.status != "available" or not manifest_plugin.manifest:
                self._finish(db, task, "failed", "El plugin ya no está disponible.", "plugin_not_available")
                return
            manifest = manifest_plugin.manifest
            tool = next((t for t in manifest.tools if t.id == task.operation), None)
            record = db.get(PluginRecord, task.plugin_id)
            if tool is None or record is None or record.admin_state != "enabled":
                self._finish(db, task, "failed", "El plugin o la herramienta ya no están habilitados.", "plugin_disabled")
                return
            plugin_dir = (self.settings.plugins_dir / manifest_plugin.folder).resolve()
            trusted_core = is_core_plugin(task.plugin_id, plugin_dir, self.settings)
            if not trusted_core and not self.settings.allow_untrusted_plugins:
                self._finish(db, task, "failed", "La ejecución de plugins no confiables está deshabilitada.", "untrusted_plugin")
                return
            try:
                validate_params(tool.params_schema, task.params)
            except SchemaError as exc:
                self._finish(db, task, "failed", str(exc), "invalid_task_params")
                return
            entrypoint = manifest.integration.entrypoint
            runner = self.runners.get(manifest.integration.type)
            if runner is None or not entrypoint:
                self._finish(db, task, "failed", "El tipo de integración todavía no se puede ejecutar.", "unsupported_integration")
                return
            script = (plugin_dir / entrypoint).resolve()
            if not script.is_relative_to(plugin_dir) or not script.is_file():
                self._finish(db, task, "failed", "El punto de entrada del plugin no es válido.", "invalid_entrypoint")
                return
            python = _plugin_python(plugin_dir, task.plugin_id, self.settings)
            if python is None:
                self._finish(db, task, "failed", "Falta el entorno Python del plugin. Instala sus dependencias por separado.", "plugin_runtime_missing")
                return
            config = db.get(Preference, f"{task.plugin_id}-config")
            config_data = config.value if config and isinstance(config.value, dict) else {}
            if trusted_core:
                config_data = {key: value for key, value in config_data.items() if key != "output_directory"}
                config_data = {
                    **config_data,
                    "_hub_data_dir": str(self.settings.data_dir),
                }
            lock = self._tool_lock(task.plugin_id, task.operation, tool.max_concurrency)

        while not lock.acquire(timeout=0.1):
            if cancel.is_set():
                with self.sessions() as db:
                    task = db.get(Task, task_id)
                    if task and task.status == "pending":
                        self._finish(db, task, "cancelled", "La tarea fue cancelada.", "task_cancelled")
                return
        try:
            if cancel.is_set():
                return
            with tempfile.TemporaryDirectory(prefix=f"hub-{task_id[:8]}-", dir=self.settings.data_dir) as temp:
                work_dir = Path(temp).resolve()
                req = RunRequest(task.plugin_id, task.operation, task.params, plugin_dir, script,
                                 work_dir, python, task.timeout_seconds or tool.timeout_seconds, config_data)
                self._run_events(task_id, req, cancel, runner)
        except Exception:
            log.exception("TaskExecutor failed for task %s", task_id)
            with self.sessions() as db:
                task = db.get(Task, task_id)
                if task and task.status in {"pending", "running"}:
                    self._finish(db, task, "failed", "Ocurrió un error al ejecutar el plugin.", "execution_failed")
        finally:
            lock.release()

    def _run_events(self, task_id: str, req: RunRequest, cancel: threading.Event, runner: PluginRunner) -> None:
        output_files = []
        done = False
        with self.sessions() as db:
            task = db.get(Task, task_id)
            if task is None or task.status != "pending":
                return
            task.status = "running"
            task.message = "Ejecutando herramienta."
            db.commit()
        last_progress_write = 0.0
        output_bytes = 0
        for event in runner.run(req, cancel):
            if cancel.is_set() or event.get("type") == "cancelled":
                with self.sessions() as db:
                    task = db.get(Task, task_id)
                    if task and task.status == "running":
                        self._finish(db, task, "cancelled", "La tarea fue cancelada.", "task_cancelled")
                return
            kind = event["type"]
            if kind == "progress":
                now = time.monotonic()
                if now - last_progress_write < PROGRESS_WRITE_INTERVAL and event["value"] < 1:
                    continue
                with self.sessions() as db:
                    task = db.get(Task, task_id)
                    if task and task.status == "running":
                        task.progress = event["value"]
                        task.message = event["message"] or "Ejecutando herramienta."
                        db.commit()
                        last_progress_write = now
            elif kind == "output":
                if len(output_files) >= MAX_OUTPUT_FILES:
                    self._fail(task_id, "El plugin superó el máximo de archivos de salida.", "too_many_outputs")
                    return
                output = _safe_output(req.work_dir, event["path"])
                if output is None:
                    self._fail(task_id, "El plugin declaró un archivo de salida inválido.", "invalid_output")
                    return
                output_bytes += output.stat().st_size
                if output_bytes > MAX_OUTPUT_TOTAL_BYTES:
                    self._fail(task_id, "El plugin superó el tamaño total permitido para archivos de salida.", "output_size_limit")
                    return
                output_files.append((output, event["display_name"]))
            elif kind == "error":
                self._fail(task_id, event["message"], event["code"])
                return
            elif kind == "done":
                done = True
        if not done:
            self._fail(task_id, "El plugin terminó sin confirmar la tarea.", "plugin_crashed")
            return
        if cancel.is_set():
            with self.sessions() as db:
                task = db.get(Task, task_id)
                if task and task.status == "running":
                    self._finish(db, task, "cancelled", "La tarea fue cancelada.", "task_cancelled")
            return
        try:
            with self.sessions() as db:
                task = db.get(Task, task_id)
                if task is None or task.status != "running":
                    return
                for source, name in output_files:
                    db.add(self.storage.store(source, task_id=task_id, display_name=name))
                task.progress = 1.0
                self._finish(db, task, "completed", "Tarea completada.")
        except OSError:
            log.exception("Could not store output for task %s", task_id)
            self._fail(task_id, "No se pudieron guardar los archivos de salida.", "file_storage_failed")

    def _fail(self, task_id: str, message: str, code: str) -> None:
        with self.sessions() as db:
            task = db.get(Task, task_id)
            if task and task.status in {"pending", "running"}:
                self._finish(db, task, "failed", message[:500], code[:64])

    @staticmethod
    def _finish(db: Session, task: Task, status: str, message: str, code: str | None = None) -> None:
        task.status = status
        task.message = message
        task.error = {"code": code, "message": message} if code else None
        task.finished_at = utcnow()
        db.commit()

    def _tool_lock(self, plugin_id: str, tool_id: str, limit: int) -> threading.BoundedSemaphore:
        with self._lock:
            return self._tool_locks.setdefault((plugin_id, tool_id), threading.BoundedSemaphore(limit))


def validate_task_request(registry: PluginRegistry, settings: Settings, db: Session,
                          plugin_id: str, tool_id: str, params: dict[str, Any]):
    plugin = registry.get(plugin_id)
    if plugin is None or plugin.status != "available" or plugin.manifest is None:
        raise AppError(404, "plugin_not_found", "El plugin no está disponible.")
    record = db.get(PluginRecord, plugin_id)
    if record is None or record.admin_state != "enabled":
        raise AppError(409, "plugin_disabled", "Habilita el plugin antes de ejecutar herramientas.")
    plugin_dir = (settings.plugins_dir / plugin.folder).resolve()
    if not is_core_plugin(plugin_id, plugin_dir, settings) and not settings.allow_untrusted_plugins:
        raise AppError(403, "untrusted_plugins_disabled", "La ejecución de plugins no confiables está deshabilitada.")
    tool = next((item for item in plugin.manifest.tools if item.id == tool_id), None)
    if tool is None:
        raise AppError(404, "tool_not_found", "La herramienta no existe en ese plugin.")
    try:
        validate_params(tool.params_schema, params)
    except SchemaError as exc:
        raise AppError(422, "invalid_task_params", str(exc)) from None
    if plugin.manifest.integration.type not in SUPPORTED_RUNNERS or not plugin.manifest.integration.entrypoint:
        raise AppError(409, "unsupported_integration", "La integración de esta herramienta todavía no se puede ejecutar.")
    return tool


def new_task(plugin_id: str, tool_id: str, params: dict[str, Any], timeout_seconds: int) -> Task:
    return Task(id=str(uuid.uuid4()), plugin_id=plugin_id, operation=tool_id,
                status="pending", message="Tarea en cola.", params=params,
                timeout_seconds=timeout_seconds)


def _plugin_python(plugin_dir: Path, plugin_id: str, settings: Settings) -> str | None:
    # This allowlist is code-owned: a manifest cannot grant itself core trust.
    if is_core_plugin(plugin_id, plugin_dir, settings):
        return sys.executable
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    executable = plugin_dir / ".venv" / relative
    return str(executable) if executable.is_file() else None


def _safe_output(work_dir: Path, relative: str) -> Path | None:
    raw = Path(relative)
    if raw.is_absolute():
        return None
    path = (work_dir / raw).resolve()
    if (not path.is_relative_to(work_dir) or not path.is_file()
            or path.stat().st_size > MAX_OUTPUT_FILE_BYTES):
        return None
    return path
