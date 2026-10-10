from __future__ import annotations

import mimetypes
import shutil
import uuid
from typing import Protocol
from pathlib import Path

from app.db.session import StoredFile, utcnow


class FileStorage(Protocol):
    def store(self, source: Path, *, task_id: str, display_name: str) -> StoredFile: ...


class LocalFileStorage:
    """Copies validated plugin output into Hub-managed storage."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, source: Path, *, task_id: str, display_name: str) -> StoredFile:
        file_id = str(uuid.uuid4())
        suffix = source.suffix[:20]
        key = f"{file_id}{suffix}"
        destination = self.root / key
        shutil.copy2(source, destination)
        return StoredFile(
            id=file_id,
            task_id=task_id,
            display_name=Path(display_name).name[:255],
            size_bytes=destination.stat().st_size,
            mime_type=mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
            storage_key=key,
            created_at=utcnow(),
        )
