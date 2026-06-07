from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.domain.dto.message_result import MessageResult
from src.domain.ports.auth_services_port import EmailPort, PasswordHasherPort
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class RequestPasswordReset:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        email_service: EmailPort,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._email_service = email_service

    async def execute(self, email: str) -> MessageResult:
        user = await self._repo.get_by_email(email)
        if not user:
            raise ValueError("Email not found")

        token = self._password_hasher.generate_token()
        token_hash = self._password_hasher.hash_token(token)
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await self._repo.create_confirmation(
            user.id, token_hash, exp, purpose="password_reset"
        )

        try:
            await self._email_service.send_reset_email(
                user.email, token, user.locale or "pt-BR"
            )
        except Exception as e:
            log_event(
                logger, logging.WARNING, "password_reset_email_failed", error=str(e)
            )

        log_event(
            logger,
            logging.INFO,
            "password_reset_request_completed",
            email=mask_email(user.email),
        )

        return MessageResult(message="Password reset email sent")
