from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class ListPublicSuggestions:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._doc_repo = doc_repo

    async def execute(self, user_id: str, limit: int = 100) -> list[DocumentSuggestion]:
        suggestions = await self._suggestion_repo.list_all(
            status="approved", user_id=user_id, limit=limit
        )
        doc_ids = [s.document_id for s in suggestions if s.document_id]
        if doc_ids:
            docs = await self._doc_repo.get_many(doc_ids)
            ingested_map = {d.id: d.ingested for d in docs}
            for s in suggestions:
                if s.document_id:
                    s.ingested = ingested_map.get(s.document_id, False)
        return suggestions
