from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.application.suggestions._guard import require_pending_suggestion
from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.auth_services_port import EmailPort
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.suggestions")


class AdminRejectDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        email_service: EmailPort,
        user_repo: UserRepository,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._email_service = email_service
        self._user_repo = user_repo

    async def execute(
        self,
        suggestion_id: str,
        reviewed_by: str,
        admin_comment: str | None = None,
    ) -> DocumentSuggestion:
        await require_pending_suggestion(self._suggestion_repo, suggestion_id)

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

        await self._notify_submitter(updated, admin_comment.strip())

        return updated

    async def _notify_submitter(
        self, suggestion: DocumentSuggestion, admin_comment: str
    ) -> None:
        try:
            user = await self._user_repo.get_by_id(suggestion.user_id)
            if user is None:
                return

            await self._email_service.send_suggestion_rejected_notification(
                user_email=user.email,
                title=suggestion.title or "",
                admin_comment=admin_comment,
                locale=user.locale,
            )
        except Exception as e:
            log_event(
                logger,
                logging.WARNING,
                "rejection_email_failed",
                user_id=suggestion.user_id,
                error=e,
            )
