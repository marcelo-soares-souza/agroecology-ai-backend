from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


async def require_pending_suggestion(
    repo: DocumentSuggestionRepository, suggestion_id: str
) -> DocumentSuggestion:
    suggestion = await repo.get(suggestion_id)
    if suggestion is None:
        raise ValueError("Suggestion not found")
    if suggestion.status != "pending":
        raise ValueError("Only pending suggestions can be modified")
    return suggestion
