from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document_academic_metadata import (
    DocumentAcademicMetadata,
    DocumentAcademicMetadataUpsert,
)


class DocumentAcademicMetadataRepository(ABC):
    @abstractmethod
    async def get(self, document_id: str) -> DocumentAcademicMetadata | None:
        """Get academic metadata for a document."""

    @abstractmethod
    async def get_many(
        self, document_ids: list[str]
    ) -> dict[str, DocumentAcademicMetadata]:
        """Get academic metadata for multiple documents."""

    @abstractmethod
    async def exists(self, document_id: str) -> bool:
        """Return whether academic metadata already exists for a document."""

    @abstractmethod
    async def count_all(self) -> int:
        """Return how many documents have stored academic metadata."""

    @abstractmethod
    async def list_publication_years(self, min_year: int, max_year: int) -> list[int]:
        """Return distinct publication years in descending order."""

    @abstractmethod
    async def upsert(
        self, metadata: DocumentAcademicMetadataUpsert
    ) -> DocumentAcademicMetadata:
        """Create or update academic metadata."""
