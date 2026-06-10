from __future__ import annotations

from abc import ABC, abstractmethod


class JobQueuePort(ABC):
    """Port for enqueuing and monitoring background jobs.

    Decouples job submission from the underlying queue implementation.
    """

    @abstractmethod
    def enqueue(
        self,
        job_type: str,
        payload: dict,
        delay_seconds: int = 0,
        max_retries: int | None = None,
    ) -> str:
        """Enqueue a new background job.

        Args:
            job_type: The job type identifier.
            payload: The job payload.
            delay_seconds: Optional delay before the job becomes eligible.
            max_retries: Maximum retry attempts for the job.

        Returns:
            The job's unique identifier.
        """

    @abstractmethod
    def count_by_status(self, job_type: str) -> dict[str, int]:
        """Get a breakdown of job counts by status.

        Args:
            job_type: The job type to query.

        Returns:
            A dict mapping status strings to their counts.
        """
