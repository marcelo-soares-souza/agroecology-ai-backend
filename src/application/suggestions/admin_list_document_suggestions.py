from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)


class AdminListDocumentSuggestions:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self,
        status: str | None = None,
        user_id: str | None = None,
        has_pdf: bool | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentSuggestion]:
        if status is not None and status not in ("pending", "approved", "rejected"):
            raise ValueError(f"Invalid status: {status}")

        return await self._suggestion_repo.list_all(
            status=status,
            user_id=user_id,
            has_pdf=has_pdf,
            q=q,
            limit=limit,
            offset=offset,
        )
