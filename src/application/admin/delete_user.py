from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class DeleteUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: str) -> UserDTO | None:
        user = await self._repo.delete(user_id)
        if not user:
            return None
        return UserDTO.minimal(user)
