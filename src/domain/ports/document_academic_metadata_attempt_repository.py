from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document_academic_metadata import (
    DocumentAcademicMetadataAttempt,
)


class DocumentAcademicMetadataAttemptRepository(ABC):
    @abstractmethod
    async def exists(self, document_id: str) -> bool:
        """Return whether a document has already been attempted."""

    @abstractmethod
    async def record(
        self,
        document_id: str,
        status: str,
        last_error: str | None = None,
    ) -> DocumentAcademicMetadataAttempt:
        """Record the latest academic metadata extraction attempt."""
