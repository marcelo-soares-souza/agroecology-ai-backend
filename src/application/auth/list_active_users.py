from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class ListActiveUsers:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self) -> list[UserDTO]:
        users = await self._user_repo.list_active()
        return [
            UserDTO.from_user(
                u,
                avatar_url=f"/api/v1/users/{u.slug}/profile/avatar/file"
                if u.avatar_path
                else None,
            )
            for u in users
        ]

    async def execute_paginated(
        self, q: str | None, limit: int, offset: int
    ) -> tuple[list[UserDTO], int]:
        users, total = await self._user_repo.list_active_paginated(q, limit, offset)
        return [
            UserDTO.from_user(
                u,
                avatar_url=f"/api/v1/users/{u.slug}/profile/avatar/file"
                if u.avatar_path
                else None,
            )
            for u in users
        ], total
