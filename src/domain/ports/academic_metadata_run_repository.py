from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document_academic_metadata import AcademicMetadataRun


class AcademicMetadataRunRepository(ABC):
    @abstractmethod
    async def create_run(self, delay_seconds: int) -> AcademicMetadataRun:
        """Create a queued academic metadata extraction run."""

    @abstractmethod
    async def set_job_id(self, run_id: str, job_id: str) -> AcademicMetadataRun | None:
        """Associate a queued job with the run."""

    @abstractmethod
    async def mark_started(
        self, run_id: str, documents_total: int
    ) -> AcademicMetadataRun | None:
        """Mark the run as processing."""

    @abstractmethod
    async def update_progress(
        self,
        run_id: str,
        documents_processed: int,
        documents_enriched: int,
        documents_skipped: int,
        documents_failed: int,
        current_document_id: str | None,
    ) -> AcademicMetadataRun | None:
        """Update run progress counters."""

    @abstractmethod
    async def mark_done(self, run_id: str) -> AcademicMetadataRun | None:
        """Mark the run as completed."""

    @abstractmethod
    async def mark_error(self, run_id: str, error: str) -> AcademicMetadataRun | None:
        """Mark the run as failed."""

    @abstractmethod
    async def has_active_run(self) -> bool:
        """Return whether a run is queued or processing."""

    @abstractmethod
    async def get_active_run(self) -> AcademicMetadataRun | None:
        """Get the current active run, if any."""

    @abstractmethod
    async def get_latest_run(self) -> AcademicMetadataRun | None:
        """Get the most recent run."""

    @abstractmethod
    async def get(self, run_id: str) -> AcademicMetadataRun | None:
        """Get a run by id."""
