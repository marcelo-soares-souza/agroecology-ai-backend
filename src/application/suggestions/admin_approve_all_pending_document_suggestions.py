from __future__ import annotations

from src.application.suggestions.admin_approve_document_suggestion import (
    AdminApproveDocumentSuggestion,
)
from src.domain.dto.suggestion_result import ApprovalFailure, BulkApprovalResult
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class AdminApproveAllPendingDocumentSuggestions:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        approve_suggestion: AdminApproveDocumentSuggestion,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._approve_suggestion = approve_suggestion

    async def execute(self, reviewed_by: str) -> BulkApprovalResult:
        pending_ids = await self._suggestion_repo.list_pending_ids()
        failures: list[ApprovalFailure] = []
        approved_count = 0

        for suggestion_id in pending_ids:
            try:
                await self._approve_suggestion.execute(
                    suggestion_id=suggestion_id,
                    reviewed_by=reviewed_by,
                    admin_comment=None,
                )
                approved_count += 1
            except ValueError as exc:
                failures.append(
                    ApprovalFailure(suggestion_id=suggestion_id, error=str(exc))
                )

        return BulkApprovalResult(
            total_pending=len(pending_ids),
            approved_count=approved_count,
            failed_count=len(failures),
            failures=failures,
        )
