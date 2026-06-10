from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class ListUsers:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[UserDTO]:
        users = await self._repo.list_all()
        return [
            UserDTO.from_user(
                u,
                avatar_url=f"/api/v1/users/{u.slug}/profile/avatar/file"
                if u.avatar_path
                else None,
            )
            for u in users
        ]
