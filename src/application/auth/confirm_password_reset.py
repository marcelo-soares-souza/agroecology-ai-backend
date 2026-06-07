from __future__ import annotations

from datetime import datetime, timezone

from src.domain.dto.message_result import MessageResult
from src.domain.ports.auth_services_port import PasswordHasherPort
from src.domain.ports.user_repository import UserRepository


class ConfirmPasswordReset:
    def __init__(
        self, repo: UserRepository, password_hasher: PasswordHasherPort
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher

    async def execute(self, token: str, new_password: str) -> MessageResult:
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters")

        token_hash = self._password_hasher.hash_token(token)
        stored = await self._repo.get_confirmation(token_hash, purpose="password_reset")

        if not stored:
            raise ValueError("Invalid or expired reset token")

        if stored["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Reset token expired")

        password_hash = self._password_hasher.hash_password(new_password)
        await self._repo.update(stored["user_id"], password_hash=password_hash)
        await self._repo.mark_confirmation_done(stored["id"])

        return MessageResult(message="Password reset successfully")
