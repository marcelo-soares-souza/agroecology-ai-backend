from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.ingestion_run import IngestionRun


class IngestionRepository(ABC):
    """Persistence interface for ingestion run tracking.

    Tracks the progress and outcome of document ingestion jobs
    and manages the ingested/not-ingested state of documents.
    """

    @abstractmethod
    async def create_run(self, force: bool = False) -> IngestionRun:
        """Create a new queued ingestion run.

        Args:
            force: Whether this run forces re-indexing of all documents.

        Returns:
            The newly created ingestion run with phase='queued'.
        """

    @abstractmethod
    async def set_job_id(self, run_id: str, job_id: str) -> IngestionRun | None:
        """Associate a job queue entry with an ingestion run.

        Args:
            run_id: The ingestion run's identifier.
            job_id: The job queue entry ID.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def mark_started(self, run_id: str) -> IngestionRun | None:
        """Mark an ingestion run as started (phase='processing').

        Args:
            run_id: The ingestion run's identifier.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def update_progress(
        self,
        run_id: str,
        documents_processed: int | None = None,
        chunks_generated: int | None = None,
        documents_total: int | None = None,
    ) -> IngestionRun | None:
        """Update progress counters during ingestion.

        Args:
            run_id: The ingestion run's identifier.
            documents_processed: Number of documents processed so far.
            chunks_generated: Number of chunks generated so far.
            documents_total: Total number of documents to process.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def mark_done(self, run_id: str, chunks_indexed: int) -> IngestionRun | None:
        """Mark an ingestion run as completed.

        Args:
            run_id: The ingestion run's identifier.
            chunks_indexed: Total chunks indexed in this run.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def mark_error(self, run_id: str, error: str) -> IngestionRun | None:
        """Mark an ingestion run as failed.

        Args:
            run_id: The ingestion run's identifier.
            error: The error message.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def has_active_run(self) -> bool:
        """Check whether there is an active ingestion run.

        An active run is one with phase 'queued' or 'processing'.

        Returns:
            True if an active run exists.
        """

    @abstractmethod
    async def get_active_run(self) -> IngestionRun | None:
        """Get the currently active ingestion run, if any.

        Returns the most recent run with phase 'queued' or 'processing'.

        Returns:
            The active ingestion run, or None.
        """

    @abstractmethod
    async def insert(self) -> IngestionRun:
        """Start a new ingestion run directly as 'processing'.

        Deprecated: prefer create_run() + mark_started() for new code.

        Returns:
            The newly created ingestion run.
        """

    @abstractmethod
    async def update(
        self,
        run_id: str,
        status: str,
        chunks_indexed: int = 0,
        error: str | None = None,
    ) -> IngestionRun | None:
        """Update the status and progress of an ingestion run.

        Args:
            run_id: The ingestion run's identifier.
            status: The new status.
            chunks_indexed: Number of chunks indexed so far.
            error: Optional error message if the run failed.

        Returns:
            The updated ingestion run, or None if not found.
        """

    @abstractmethod
    async def list_all(self) -> list[IngestionRun]:
        """List all ingestion runs.

        Returns:
            A list of all ingestion runs.
        """

    @abstractmethod
    async def get(self, run_id: str) -> IngestionRun | None:
        """Retrieve an ingestion run by its ID.

        Args:
            run_id: The ingestion run's identifier.

        Returns:
            The ingestion run, or None if not found.
        """

    @abstractmethod
    async def get_ingested_ids(self, doc_ids: set[str]) -> set[str]:
        """Check which of the given document IDs have already been ingested.

        Args:
            doc_ids: A set of document IDs to check.

        Returns:
            The subset of IDs that are already marked as ingested.
        """

    @abstractmethod
    async def mark_as_ingested(self, doc_ids: set[str]) -> None:
        """Mark the given document IDs as ingested.

        Args:
            doc_ids: A set of document IDs to mark.
        """

    @abstractmethod
    async def mark_all_not_ingested(self) -> None:
        """Reset the ingested flag on all documents."""
