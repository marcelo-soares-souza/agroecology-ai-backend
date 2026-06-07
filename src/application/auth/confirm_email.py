from __future__ import annotations

from datetime import datetime, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.password_hasher import hash_token


class ConfirmEmail:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, token: str) -> dict:
        token_hash = hash_token(token)
        stored = await self._repo.get_confirmation(token_hash)

        if not stored:
            raise ValueError("Invalid or already used token")

        if stored["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Confirmation token expired")

        await self._repo.mark_confirmation_done(stored["id"])
        await self._repo.confirm_email(stored["user_id"])

        return {"message": "Email confirmed successfully"}
