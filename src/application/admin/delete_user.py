from __future__ import annotations

from src.domain.ports.user_repository import UserRepository


class DeleteUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: str) -> dict | None:
        user = await self._repo.delete(user_id)
        if not user:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
        }
