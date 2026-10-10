from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class RunRequest:
    plugin_id: str
    tool_id: str
    params: dict[str, Any]
    plugin_dir: Path
    entrypoint: Path
    work_dir: Path
    python: str
    timeout_seconds: int
    config: dict[str, Any]

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "tool": self.tool_id,
            "params": self.params,
            "work_dir": str(self.work_dir),
            "config": self.config,
        }


class PluginRunner(Protocol):
    def run(self, req: RunRequest, cancel: Event) -> Iterator[dict[str, Any]]: ...
