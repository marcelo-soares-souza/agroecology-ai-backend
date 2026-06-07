from __future__ import annotations

from src.domain.ports.user_repository import UserRepository


class LogoutUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: str) -> None:
        await self._repo.revoke_all_refresh_tokens(user_id)
