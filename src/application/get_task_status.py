from __future__ import annotations

from src.domain.dto.task_dto import TaskDTO
from src.domain.ports.task_manager_port import TaskManagerPort


class GetTaskStatus:
    def __init__(self, task_manager: TaskManagerPort) -> None:
        self._task_manager = task_manager

    def get(self, task_id: str) -> TaskDTO | None:
        return self._task_manager.get(task_id)

    def active_count(self) -> int:
        return self._task_manager.active_count()
