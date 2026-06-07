from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.human_check import verify_challenge
from src.infrastructure.auth.password_hasher import (
    generate_token,
    hash_password,
    hash_token,
)
from src.infrastructure.email.smtp_service import send_confirmation_email
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class RegisterUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        email: str,
        full_name: str,
        password: str,
        locale: str,
        challenge_id: str,
        challenge_answer: str,
    ) -> dict:
        if not verify_challenge(challenge_id, challenge_answer):
            raise ValueError("Human verification failed")

        existing = await self._repo.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        slug = await self._generate_slug(full_name)
        password_hash = hash_password(password)
        user = await self._repo.create(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            slug=slug,
            locale=locale,
            role_key="user",
        )

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
            "registration_completed",
            user_id=user.id,
            email=mask_email(user.email),
            slug=user.slug,
            locale=user.locale,
        )

        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "slug": user.slug,
            "locale": user.locale,
            "status": user.status,
        }

    async def _generate_slug(self, full_name: str) -> str:
        base = (
            unicodedata.normalize("NFKD", full_name)
            .encode("ascii", "ignore")
            .decode()
            .strip()
            .lower()
        )
        base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        if not base:
            base = "user"
        candidate = base
        suffix = 1
        while await self._repo.get_by_slug(candidate) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate
