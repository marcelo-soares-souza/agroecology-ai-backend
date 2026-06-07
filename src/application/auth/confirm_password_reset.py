from __future__ import annotations

from datetime import datetime, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.password_hasher import hash_password, hash_token


class ConfirmPasswordReset:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, token: str, new_password: str) -> dict:
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters")

        token_hash = hash_token(token)
        stored = await self._repo.get_confirmation(token_hash)

        if not stored:
            raise ValueError("Invalid or expired reset token")

        if stored["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Reset token expired")

        password_hash = hash_password(new_password)
        await self._repo.update(stored["user_id"], password_hash=password_hash)
        await self._repo.mark_confirmation_done(stored["id"])

        return {"message": "Password reset successfully"}
