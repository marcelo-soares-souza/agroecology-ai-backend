from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.auth_services_port import (
    EmailPort,
    HumanCheckPort,
    PasswordHasherPort,
)
from src.domain.ports.user_repository import UserRepository
from src.shared.email_utils import validate_email
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class RegisterUser:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        human_check: HumanCheckPort,
        email_service: EmailPort,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._human_check = human_check
        self._email_service = email_service

    async def execute(
        self,
        email: str,
        full_name: str,
        password: str,
        locale: str,
        challenge_id: str,
        challenge_answer: str,
        privacy_policy_accepted: bool = False,
        tos_accepted: bool = False,
    ) -> UserDTO:
        email = validate_email(email)

        if not self._human_check.verify_challenge(challenge_id, challenge_answer):
            raise ValueError("Human verification failed")

        if not privacy_policy_accepted:
            raise ValueError("Privacy Policy must be accepted")

        if not tos_accepted:
            raise ValueError("Terms of Service must be accepted")

        existing = await self._repo.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        slug = await self._generate_slug(full_name)
        password_hash = self._password_hasher.hash_password(password)
        user = await self._repo.create(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            slug=slug,
            locale=locale,
            role_key="user",
            privacy_policy_accepted=privacy_policy_accepted,
            tos_accepted=tos_accepted,
        )

        token = self._password_hasher.generate_token()
        token_hash = self._password_hasher.hash_token(token)
        exp = datetime.now(timezone.utc) + timedelta(hours=24)
        await self._repo.create_confirmation(user.id, token_hash, exp)

        try:
            await self._email_service.send_confirmation_email(
                user.email, token, user.locale or "pt-BR"
            )
            await self._email_service.send_admin_new_user_notification(
                user.email, user.full_name, user.locale or "pt-BR"
            )
        except Exception as e:
            log_event(
                logger, logging.WARNING, "registration_email_failed", error=str(e)
            )

        log_event(
            logger,
            logging.INFO,
            "registration_completed",
            user_id=user.id,
            email=mask_email(user.email),
            slug=user.slug,
            locale=user.locale,
        )

        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        return UserDTO.from_user(user, avatar_url=avatar_url)

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
