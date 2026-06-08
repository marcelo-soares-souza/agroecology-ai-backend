from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.document import Document
from src.domain.models.document_suggestion import DocumentSuggestion


@dataclass(frozen=True)
class ApprovalResult:
    suggestion: DocumentSuggestion
    document: Document
