from __future__ import annotations

import logging

from src.application.config import AvatarStorageConfig, SuggestionStorageConfig
from src.domain.dto.user_dto import UserDTO
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.admin")


class DeleteUser:
    def __init__(
        self,
        repo: UserRepository,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
        avatar_config: AvatarStorageConfig,
        suggestion_config: SuggestionStorageConfig,
    ) -> None:
        self._repo = repo
        self._suggestion_repo = suggestion_repo
        self._storage = storage
        self._avatar_config = avatar_config
        self._suggestion_config = suggestion_config

    async def execute(self, actor_user_id: str, user_id: str) -> UserDTO | None:
        if user_id == actor_user_id:
            raise ValueError("Cannot delete yourself")

        existing = await self._repo.get_by_id(user_id)
        if not existing:
            return None

        if existing.avatar_path:
            try:
                await self._storage.delete(
                    self._avatar_config.storage_directory(user_id),
                    self._avatar_config.file_name,
                    self._avatar_config.file_extension,
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "admin_user_avatar_delete_failed",
                    user_id=user_id,
                    error=exc,
                )

        suggestions = await self._suggestion_repo.list_for_user(user_id)
        for suggestion in suggestions:
            if suggestion.original_filename is None:
                continue
            try:
                await self._storage.delete(
                    self._suggestion_config.pending_directory,
                    suggestion.id,
                    ".pdf",
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "admin_suggestion_attachment_delete_failed",
                    suggestion_id=suggestion.id,
                    error=exc,
                )

        user = await self._repo.anonymize_user(
            user_id, request_source="admin_delete"
        )
        if not user:
            return None
        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        return UserDTO.minimal(user, avatar_url=avatar_url)
