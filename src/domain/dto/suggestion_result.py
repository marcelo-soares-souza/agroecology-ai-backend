from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.document import Document
from src.domain.models.document_suggestion import DocumentSuggestion


@dataclass(frozen=True)
class ApprovalResult:
    """Result of approving a document suggestion.

    Attributes:
        suggestion: The updated suggestion with approved status.
        document: The newly created document from the suggestion.
    """

    suggestion: DocumentSuggestion
    document: Document


@dataclass(frozen=True)
class ApprovalFailure:
    """Failure produced while approving suggestions in bulk."""

    suggestion_id: str
    error: str


@dataclass(frozen=True)
class BulkApprovalResult:
    """Result of approving all pending document suggestions."""

    total_pending: int
    approved_count: int
    failed_count: int
    failures: list[ApprovalFailure]
