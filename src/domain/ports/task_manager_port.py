from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.task_dto import TaskDTO


class TaskManagerPort(ABC):
    @abstractmethod
    def get(self, task_id: str) -> TaskDTO | None: ...

    @abstractmethod
    def active_count(self) -> int: ...
