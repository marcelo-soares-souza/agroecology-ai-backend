from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IngestionRun:
    """Records the state and outcome of a document ingestion job.

    Attributes:
        id: The ingestion run's unique identifier.
        status: The current status of the run.
        phase: The current phase of the run (queued, processing, done, error).
        chunks_indexed: Number of chunks successfully indexed.
        chunks_generated: Number of chunks generated.
        documents_total: Total number of documents to process.
        documents_processed: Number of documents processed so far.
        force: Whether this was a force rebuild.
        job_id: The job queue entry, if any.
        started_at: Timestamp of when the run started.
        finished_at: Timestamp of when the run finished.
        queued_at: Timestamp of when the run was queued.
        error: Error message if the run failed.
    """

    id: str
    status: str
    chunks_indexed: int
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    phase: str = "processing"
    chunks_generated: int = 0
    documents_total: int = 0
    documents_processed: int = 0
    force: bool = False
    job_id: str | None = None
    queued_at: datetime | None = None
