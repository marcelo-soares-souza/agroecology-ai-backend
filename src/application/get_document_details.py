from __future__ import annotations

from src.domain.dto.document_result import DocumentDetailsResult
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class GetDocumentDetails:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        suggestion_repo: DocumentSuggestionRepository,
        academic_metadata_repo: DocumentAcademicMetadataRepository,
    ) -> None:
        self._doc_repo = doc_repo
        self._suggestion_repo = suggestion_repo
        self._academic_metadata_repo = academic_metadata_repo

    async def execute(self, doc_id: str) -> DocumentDetailsResult | None:
        doc = await self._doc_repo.get(doc_id)
        if not doc:
            return None

        suggestion = await self._suggestion_repo.get_by_document_id(doc_id)
        academic_metadata = await self._academic_metadata_repo.get(doc_id)
        return DocumentDetailsResult(
            document=doc,
            academic_metadata=academic_metadata,
            suggested_by_user_id=suggestion.user_id if suggestion else None,
            suggested_by_user_name=suggestion.user_name if suggestion else None,
            suggested_by_user_slug=suggestion.user_slug if suggestion else None,
        )
