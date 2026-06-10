from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IngestionRun:
    """Records the state and outcome of a document ingestion job.

    Attributes:
        id: The ingestion run's unique identifier.
        status: The current status of the run.
        chunks_indexed: Number of chunks successfully indexed.
        started_at: Timestamp of when the run started.
        finished_at: Timestamp of when the run finished.
        error: Error message if the run failed.
    """

    id: str
    status: str
    chunks_indexed: int
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
