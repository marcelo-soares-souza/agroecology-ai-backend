from __future__ import annotations

from datetime import datetime, timezone

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)


class AdminRejectDocumentSuggestion:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self,
        suggestion_id: str,
        reviewed_by: str,
        admin_comment: str | None = None,
    ) -> DocumentSuggestion:
        suggestion = await self._suggestion_repo.get(suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can be rejected")

        if not admin_comment or not admin_comment.strip():
            raise ValueError("Admin comment is required when rejecting")

        reviewed_at = datetime.now(timezone.utc)

        updated = await self._suggestion_repo.mark_rejected(
            suggestion_id=suggestion_id,
            admin_comment=admin_comment.strip(),
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
        )

        if updated is None:
            raise ValueError("Suggestion not found")

        return updated
