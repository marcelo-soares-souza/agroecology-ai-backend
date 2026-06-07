from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.password_hasher import generate_token, hash_token
from src.infrastructure.email.smtp_service import send_confirmation_email
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class ResendConfirmationEmail:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, email: str) -> dict:
        user = await self._repo.get_by_email(email)
        if not user:
            raise ValueError("Email not found")

        if user.email_confirmed_at is not None:
            raise ValueError("Email already confirmed")

        token = generate_token()
        token_hash = hash_token(token)
        exp = datetime.now(timezone.utc) + timedelta(hours=24)
        await self._repo.create_confirmation(user.id, token_hash, exp)

        try:
            import asyncio

            asyncio.create_task(
                send_confirmation_email(user.email, token, user.locale or "pt-BR")
            )
        except Exception:
            pass

        log_event(
            logger,
            logging.INFO,
            "confirmation_email_resend_completed",
            email=mask_email(user.email),
        )

        return {"message": "Confirmation email sent"}
