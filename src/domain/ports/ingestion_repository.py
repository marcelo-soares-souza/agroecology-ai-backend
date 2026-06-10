from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.ingestion_run import IngestionRun


class IngestionRepository(ABC):
    """Persistence interface for ingestion run tracking.

    Tracks the progress and outcome of document ingestion jobs
    and manages the ingested/not-ingested state of documents.
    """

    @abstractmethod
    async def insert(self) -> IngestionRun:
        """Start a new ingestion run.

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
