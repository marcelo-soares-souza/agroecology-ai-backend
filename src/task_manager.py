import os
import threading
import time
from dataclasses import dataclass, field


def uuid7() -> str:
    ts = int(time.time() * 1000)
    rand = os.urandom(10)
    ts_bytes = ts.to_bytes(6, "big")
    b = bytearray(ts_bytes + rand)
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return (
        f"{int.from_bytes(b[0:4], 'big'):08x}-"
        f"{int.from_bytes(b[4:6], 'big'):04x}-"
        f"{b[6]:02x}{b[7]:02x}-"
        f"{b[8]:02x}{b[9]:02x}-"
        f"{b[10:].hex()}"
    )

from .config import CLEANUP_INTERVAL, TASK_TTL


@dataclass
class Task:
    task_id: str
    status: str  # "processing" | "done" | "error"
    question: str
    top_k: int
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True
        )
        self._cleanup_thread.start()

    def create(self, question: str, top_k: int) -> str:
        task_id = uuid7()
        task = Task(
            task_id=task_id,
            status="processing",
            question=question,
            top_k=top_k,
        )
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update(
        self,
        task_id: str,
        status: str,
        answer: str | None = None,
        sources: list[dict] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.status = status
            task.answer = answer
            task.sources = sources
            task.error = error
            if status in ("done", "error"):
                task.completed_at = time.time()

    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for t in self._tasks.values() if t.status == "processing"
            )

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(CLEANUP_INTERVAL)
            self._cleanup()

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                tid
                for tid, t in self._tasks.items()
                if now - t.created_at > TASK_TTL
            ]
            for tid in expired:
                del self._tasks[tid]

    def shutdown(self) -> None:
        self._running = False
