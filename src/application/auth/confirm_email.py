from __future__ import annotations

from datetime import datetime, timezone

from src.domain.dto.message_result import MessageResult
from src.domain.ports.auth_services_port import PasswordHasherPort
from src.domain.ports.user_repository import UserRepository


class ConfirmEmail:
    def __init__(
        self, repo: UserRepository, password_hasher: PasswordHasherPort
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher

    async def execute(self, token: str) -> MessageResult:
        token_hash = self._password_hasher.hash_token(token)
        stored = await self._repo.get_confirmation(token_hash)

        if not stored:
            raise ValueError("Invalid or already used token")

        if stored["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Confirmation token expired")

        await self._repo.mark_confirmation_done(stored["id"])
        await self._repo.confirm_email(stored["user_id"])

        return MessageResult(message="Email confirmed successfully")
