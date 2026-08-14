from __future__ import annotations

from datetime import UTC, datetime

from src.domain.dto.document_result import DocumentListItem, DocumentListResult
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_repository import DocumentRepository


class ListDocuments:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        academic_metadata_repo: DocumentAcademicMetadataRepository,
        publication_year_min: int = 1985,
    ) -> None:
        self._doc_repo = doc_repo
        self._academic_metadata_repo = academic_metadata_repo
        self._publication_year_min = publication_year_min

    async def execute(
        self,
        q: str | None,
        limit: int,
        offset: int,
        full_metadata: bool = False,
        publication_year: int | None = None,
    ) -> DocumentListResult:
        current_year = datetime.now(UTC).year
        if publication_year is not None and (
            publication_year < self._publication_year_min
            or publication_year > current_year
        ):
            raise ValueError(
                "publication_year must be between "
                f"{self._publication_year_min} and {current_year}"
            )

        docs, total = await self._doc_repo.list_paginated(
            q=q,
            limit=limit,
            offset=offset,
            full_metadata=full_metadata,
            publication_year=publication_year,
        )
        metadata_map = await self._academic_metadata_repo.get_many(
            [doc.id for doc in docs]
        )
        return DocumentListResult(
            items=[
                DocumentListItem(
                    document=doc,
                    academic_metadata=metadata_map.get(doc.id),
                )
                for doc in docs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
