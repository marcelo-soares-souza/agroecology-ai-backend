from __future__ import annotations

from datetime import UTC, datetime

from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)


class ListDocumentPublicationYears:
    def __init__(
        self,
        academic_metadata_repo: DocumentAcademicMetadataRepository,
        publication_year_min: int = 1985,
    ) -> None:
        self._academic_metadata_repo = academic_metadata_repo
        self._publication_year_min = publication_year_min

    async def execute(self) -> list[int]:
        return await self._academic_metadata_repo.list_publication_years(
            self._publication_year_min,
            datetime.now(UTC).year,
        )
