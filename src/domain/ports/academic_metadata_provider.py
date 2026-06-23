from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document_academic_metadata import AcademicMetadataCandidate


class AcademicMetadataProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier used for persistence and audit."""

    @abstractmethod
    async def search(
        self, title: str, limit: int = 5
    ) -> list[AcademicMetadataCandidate]:
        """Search external academic metadata by title."""
