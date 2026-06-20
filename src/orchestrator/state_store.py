"""
Centralized state for the task graph.

Every subagent's state used to live wherever that subagent happened to
keep it. When a compliance workflow needed a complete decision log
reconstructed after the fact, there was no single place to reconstruct it
from. This is that single place -- in-memory here, backed by DynamoDB in
the prod deployment (see ARCHITECTURE.md).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TaskRecord:
    task_id: str
    agent: str
    status: str  # "pending" | "ok" | "failed" | "retrying"
    attempts: int = 0
    history: list[dict] = field(default_factory=list)


class StateStore:
    """Single source of truth for task state and the decision log.
    Not thread-safe by design -- the orchestrator is the only writer."""

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}

    def record(self, task_id: str, agent: str, status: str, detail: dict | None = None) -> None:
        rec = self._tasks.setdefault(task_id, TaskRecord(task_id=task_id, agent=agent, status=status))
        rec.status = status
        rec.history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "status": status,
            "detail": detail or {},
        })

    def record_attempt(self, task_id: str) -> int:
        rec = self._tasks.get(task_id)
        if rec is None:
            return 0
        rec.attempts += 1
        return rec.attempts

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def decision_log(self, task_id: str) -> list[dict]:
        rec = self._tasks.get(task_id)
        return rec.history if rec else []
