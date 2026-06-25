from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from src.domain.ports.auth_services_port import EmailPort, PasswordHasherPort
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.user_repository import UserRepository
from src.shared.config import AVATAR_DIR, DATA_DIR_PENDING
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class RequestDeleteAccount:
    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasherPort,
        email_service: EmailPort,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._email_service = email_service

    async def execute(self, user_id: str) -> None:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        if user.status == "deleted":
            raise ValueError("Account already deleted")

        token = self._password_hasher.generate_token()
        token_hash = self._password_hasher.hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await self._user_repo.create_confirmation(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            purpose="delete_account",
        )

        await self._email_service.send_delete_account_confirmation(
            to_email=user.email,
            token=token,
            locale=user.locale or "pt-BR",
        )


class ConfirmDeleteAccount:
    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasherPort,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._suggestion_repo = suggestion_repo
        self._storage = storage

    async def execute(self, token: str) -> None:
        token_hash = self._password_hasher.hash_token(token)
        confirmation = await self._user_repo.get_confirmation(
            token_hash, purpose="delete_account"
        )
        if confirmation is None:
            raise ValueError("Invalid or expired confirmation token")

        user_id = confirmation["user_id"]
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        if user.avatar_path:
            try:
                avatar_full_path = os.path.normpath(
                    os.path.join(AVATAR_DIR, user.avatar_path)
                )
                if os.path.isfile(avatar_full_path):
                    os.remove(avatar_full_path)
            except Exception:
                pass

        await self._delete_pending_suggestion_files(user_id)
        await self._user_repo.anonymize_user(user_id)
        await self._user_repo.mark_confirmation_done(confirmation["id"])

        log_event(
            logger,
            logging.INFO,
            "account_deletion_completed",
            user_id=user_id,
            email=mask_email(user.email),
        )

    async def _delete_pending_suggestion_files(self, user_id: str) -> None:
        suggestions = await self._suggestion_repo.list_for_user(user_id)
        for suggestion in suggestions:
            if suggestion.original_filename is None:
                continue
            try:
                await self._storage.delete(DATA_DIR_PENDING.name, suggestion.id, ".pdf")
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "suggestion_attachment_delete_failed",
                    suggestion_id=suggestion.id,
                    error=exc,
                )
