"""Máquina de estados de tareas."""
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}
TERMINAL = {s for s, nxt in TRANSITIONS.items() if not nxt}
STATUSES = tuple(TRANSITIONS)


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())
