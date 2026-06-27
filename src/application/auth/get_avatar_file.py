from __future__ import annotations

from src.application.config import AvatarStorageConfig
from src.domain.dto.user_dto import UserDTO
from src.domain.ports.file_storage_port import FileStoragePort


class GetAvatarFile:
    def __init__(self, storage: FileStoragePort, config: AvatarStorageConfig) -> None:
        self._storage = storage
        self._config = config

    async def execute(self, user: UserDTO) -> str | None:
        if not user.avatar_path:
            return None
        directory = self._config.storage_directory(user.id)
        if not await self._storage.exists(
            directory,
            self._config.file_name,
            self._config.file_extension,
        ):
            return None
        return self._storage.get_path(
            directory,
            self._config.file_name,
            self._config.file_extension,
        )
