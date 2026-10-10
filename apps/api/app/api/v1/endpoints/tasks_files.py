from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db, get_registry
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import StoredFile, Task
from app.modules.tasks.executor import new_task, validate_task_request
from app.modules.tasks.state import can_transition

router = APIRouter(tags=["tasks", "files"])


class CreateTaskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plugin_id: str = Field(min_length=1, max_length=64)
    tool_id: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


def _file(f: StoredFile) -> dict:
    return {
        "id": f.id, "task_id": f.task_id, "display_name": f.display_name,
        "size_bytes": f.size_bytes, "mime_type": f.mime_type,
        "created_at": f.created_at, "expires_at": f.expires_at,
    }


def _task(t: Task, files: list[StoredFile] | None = None) -> dict:
    return {
        "id": t.id, "plugin_id": t.plugin_id, "operation": t.operation, "status": t.status,
        "progress": t.progress, "message": t.message, "error": t.error,
        "cancel_requested": bool(t.cancel_requested), "timeout_seconds": t.timeout_seconds,
        "created_at": t.created_at, "finished_at": t.finished_at,
        "files": [_file(f) for f in files or []],
    }


@router.get("/tasks")
def list_tasks(
    status: Literal["pending", "running", "completed", "failed", "cancelled"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)).all()
    files_by_task: dict[str, list[StoredFile]] = {}
    if rows:
        files = db.scalars(select(StoredFile).where(StoredFile.task_id.in_([t.id for t in rows]))).all()
        for stored_file in files:
            if stored_file.task_id is not None:
                files_by_task.setdefault(stored_file.task_id, []).append(stored_file)
    active = db.scalar(select(func.count()).select_from(Task).where(Task.status.in_(("pending", "running")))) or 0
    return {"items": [_task(t, files_by_task.get(t.id, [])) for t in rows], "total": total, "active_count": active, "limit": limit, "offset": offset}


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
def create_task(
    body: CreateTaskBody,
    request: Request,
    db: Session = Depends(get_db),
    registry=Depends(get_registry),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    tool = validate_task_request(registry, settings, db, body.plugin_id, body.tool_id, body.params)
    task = new_task(body.plugin_id, body.tool_id, body.params, tool.timeout_seconds)
    db.add(task)
    db.commit()
    request.app.state.task_executor.enqueue(task.id)
    return _task(task)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    t = db.get(Task, task_id)
    if t is None:
        raise AppError(404, "task_not_found", "Tarea no encontrada.")
    if not can_transition(t.status, "cancelled"):
        raise AppError(409, "invalid_transition", f"No se puede cancelar una tarea en estado '{t.status}'.")
    t.cancel_requested = 1
    if t.status == "pending":
        t.status, t.finished_at = "cancelled", datetime.now(UTC)
    db.commit()
    request.app.state.task_executor.cancel(task_id)
    return _task(t)


@router.get("/files")
def list_files(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count()).select_from(StoredFile)) or 0
    rows = db.scalars(select(StoredFile).order_by(StoredFile.created_at.desc()).limit(limit).offset(offset)).all()
    items = [_file(f) for f in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    stored_file = db.get(StoredFile, file_id)
    if stored_file is None:
        raise AppError(404, "file_not_found", "Archivo no encontrado.")

    storage_root = (settings.data_dir / "files").resolve()
    file_path = (storage_root / stored_file.storage_key).resolve()
    if not file_path.is_relative_to(storage_root) or not file_path.is_file():
        raise AppError(404, "file_not_found", "El archivo ya no está disponible.")
    return FileResponse(
        file_path,
        filename=stored_file.display_name,
        media_type=stored_file.mime_type or "application/octet-stream",
    )
