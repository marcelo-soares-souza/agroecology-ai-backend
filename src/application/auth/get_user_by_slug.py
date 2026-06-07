from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class GetUserBySlug:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, slug_or_id: str) -> UserDTO | None:
        user = await self._repo.get_by_slug(slug_or_id)
        if not user:
            user = await self._repo.get_by_id(slug_or_id)
        if not user:
            return None
        return UserDTO.from_user(user)
