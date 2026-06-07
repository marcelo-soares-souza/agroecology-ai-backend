from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.password_hasher import generate_token, hash_token
from src.infrastructure.email.smtp_service import send_reset_email
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class RequestPasswordReset:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, email: str) -> dict:
        user = await self._repo.get_by_email(email)
        if not user:
            raise ValueError("Email not found")

        token = generate_token()
        token_hash = hash_token(token)
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await self._repo.create_confirmation(user.id, token_hash, exp)

        try:
            import asyncio

            asyncio.create_task(
                send_reset_email(user.email, token, user.locale or "pt-BR")
            )
        except Exception:
            pass

        log_event(
            logger,
            logging.INFO,
            "password_reset_request_completed",
            email=mask_email(user.email),
        )

        return {"message": "Password reset email sent"}
