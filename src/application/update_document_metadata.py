from __future__ import annotations

from src.domain.dto.document_result import DocumentDetailsResult
from src.domain.models.document import DocumentUpdate
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_repository import DocumentRepository


class UpdateDocumentMetadata:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        academic_metadata_repo: DocumentAcademicMetadataRepository,
    ) -> None:
        self._doc_repo = doc_repo
        self._academic_metadata_repo = academic_metadata_repo

    async def execute(
        self,
        doc_id: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
    ) -> DocumentDetailsResult | None:
        doc = await self._doc_repo.update(
            doc_id,
            DocumentUpdate(title=title, authors=authors, url=url),
        )
        if not doc:
            return None
        return DocumentDetailsResult(
            document=doc,
            academic_metadata=await self._academic_metadata_repo.get(doc_id),
        )

