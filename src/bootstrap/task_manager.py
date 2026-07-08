from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from src.domain.dto.task_dto import TaskDTO
from src.domain.ports.task_manager_port import TaskManagerPort
from src.shared.config import CLEANUP_INTERVAL, TASK_TTL
from src.shared.uuid7 import uuid7


@dataclass
class Task:
    task_id: str
    question: str
    top_k: int
    status: str = "processing"
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    conversation_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class TaskManager(TaskManagerPort):
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._cleanup_daemon: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._cleanup_started = False

    def start_cleanup(self) -> None:
        if self._cleanup_started:
            return

        def loop():
            while not self._stop_event.wait(timeout=CLEANUP_INTERVAL):
                self._cleanup()

        self._stop_event.clear()
        self._cleanup_started = True
        self._cleanup_daemon = threading.Thread(target=loop, daemon=True)
        self._cleanup_daemon.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._cleanup_daemon is not None:
            self._cleanup_daemon.join(timeout=5)
            self._cleanup_daemon = None
        self._cleanup_started = False

    def create(
        self,
        question: str,
        top_k: int,
        *,
        conversation_id: str | None = None,
        user_message_id: str | None = None,
        assistant_message_id: str | None = None,
    ) -> str:
        task_id = uuid7()
        task = Task(
            task_id=task_id,
            question=question,
            top_k=top_k,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def get(self, task_id: str) -> TaskDTO | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return TaskDTO(
                task_id=task.task_id,
                question=task.question,
                top_k=task.top_k,
                status=task.status,
                answer=task.answer,
                sources=task.sources,
                error=task.error,
                conversation_id=task.conversation_id,
                user_message_id=task.user_message_id,
                assistant_message_id=task.assistant_message_id,
                created_at=task.created_at,
                completed_at=task.completed_at,
            )

    def update(
        self,
        task_id: str,
        *,
        status: str,
        answer: str | None = None,
        sources: list[dict] | None = None,
        error: str | None = None,
        conversation_id: str | None = None,
        user_message_id: str | None = None,
        assistant_message_id: str | None = None,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                if answer is not None:
                    task.answer = answer
                if sources is not None:
                    task.sources = sources
                if error is not None:
                    task.error = error
                if conversation_id is not None:
                    task.conversation_id = conversation_id
                if user_message_id is not None:
                    task.user_message_id = user_message_id
                if assistant_message_id is not None:
                    task.assistant_message_id = assistant_message_id
                if status in ("done", "error"):
                    task.completed_at = time.time()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == "processing")

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                tid for tid, t in self._tasks.items() if now - t.created_at > TASK_TTL
            ]
            for tid in expired:
                del self._tasks[tid]
