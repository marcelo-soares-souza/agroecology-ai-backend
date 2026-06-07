from abc import ABC, abstractmethod


class JobQueuePort(ABC):
    @abstractmethod
    def enqueue(
        self,
        job_type: str,
        payload: dict,
        delay_seconds: int = 0,
        max_retries: int | None = None,
    ) -> str: ...

    @abstractmethod
    def count_by_status(self, job_type: str) -> dict[str, int]: ...
