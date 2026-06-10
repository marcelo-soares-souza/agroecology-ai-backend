from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskDTO:
    task_id: str
    question: str
    top_k: int
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    created_at: float = 0.0
    completed_at: float | None = None
