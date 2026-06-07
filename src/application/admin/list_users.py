from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class ListUsers:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[UserDTO]:
        users = await self._repo.list_all()
        return [UserDTO.from_user(u) for u in users]
