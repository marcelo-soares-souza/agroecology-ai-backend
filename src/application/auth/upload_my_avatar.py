from __future__ import annotations

from collections.abc import Callable

from src.application.config import AvatarStorageConfig
from src.domain.dto.user_dto import UserDTO
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.user_repository import UserRepository


class UploadMyAvatar:
    def __init__(
        self,
        user_repo: UserRepository,
        storage: FileStoragePort,
        config: AvatarStorageConfig,
        process_avatar: Callable[[bytes], bytes],
    ) -> None:
        self._user_repo = user_repo
        self._storage = storage
        self._config = config
        self._process_avatar = process_avatar

    async def execute(
        self,
        user_id: str,
        content: bytes,
        content_type: str,
    ) -> UserDTO:
        if content_type not in self._config.allowed_mime_types:
            raise ValueError("Unsupported image type. Use JPEG, PNG, or WebP.")

        if len(content) > self._config.max_file_size:
            raise ValueError("Image must not exceed 5MB.")

        try:
            processed = self._process_avatar(content)
        except Exception as e:
            raise ValueError(f"Invalid image: {e}")

        directory = self._config.storage_directory(user_id)
        await self._storage.save(
            directory,
            self._config.file_name,
            self._config.file_extension,
            processed,
        )
        avatar_path = self._storage.get_path(
            directory,
            self._config.file_name,
            self._config.file_extension,
        )

        updated = await self._user_repo.update(user_id, avatar_path=str(avatar_path))
        if not updated:
            raise ValueError("User not found")
        avatar_url = (
            f"/api/v1/users/{updated.slug}/profile/avatar/file"
            if updated.avatar_path
            else None
        )
        return UserDTO.from_user(updated, avatar_url=avatar_url)
