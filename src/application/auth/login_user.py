from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.application.auth.provision_external_user import ProvisionExternalUser
from src.domain.dto.auth_result import LoginResult
from src.domain.dto.user_dto import UserDTO
from src.domain.models.user import User
from src.domain.ports.auth_services_port import PasswordHasherPort, TokenServicePort
from src.domain.ports.identity_server_client import (
    IdentityServerClient,
    IdentityServerEmailNotConfirmed,
    IdentityServerInvalidCredentials,
    IdentityServerUnavailable,
)
from src.domain.ports.user_repository import UserRepository
from src.shared.config import REFRESH_TOKEN_TTL_DAYS
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class LoginUser:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
        identity_client: IdentityServerClient | None = None,
        provision_external_user: ProvisionExternalUser | None = None,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._identity_client = identity_client
        self._provision_external_user = provision_external_user

    async def execute(self, email: str, password: str) -> LoginResult:
        user = await self._repo.get_by_email(email)
        if not user:
            return await self._login_with_external_identity(email, password)

        if not self._password_hasher.verify_password(password, user.password_hash):
            log_event(
                logger,
                logging.WARNING,
                "local_login_failed",
                email=mask_email(email),
                reason="invalid_password",
            )
            raise ValueError("Invalid email or password")

        if user.email_confirmed_at is None:
            raise ValueError("Email not confirmed")

        if user.status != "active":
            raise ValueError("Account is not active")

        await self._repo.update_last_login(user.id)

        log_event(logger, logging.INFO, "local_login_completed", user_id=user.id)
        return await self._issue_tokens(user)

    async def _login_with_external_identity(
        self, email: str, password: str
    ) -> LoginResult:
        if not self._identity_client or not self._provision_external_user:
            log_event(
                logger,
                logging.INFO,
                "remote_login_disabled",
                email=mask_email(email),
            )
            raise ValueError("Invalid email or password")

        try:
            remote_identity = await self._identity_client.authenticate(email, password)
        except IdentityServerEmailNotConfirmed:
            log_event(
                logger,
                logging.WARNING,
                "remote_login_failed",
                email=mask_email(email),
                reason="email_not_confirmed",
            )
            raise ValueError("Email not confirmed")
        except IdentityServerInvalidCredentials:
            log_event(
                logger,
                logging.WARNING,
                "remote_login_failed",
                email=mask_email(email),
                reason="invalid_credentials",
            )
            raise ValueError("Invalid email or password")
        except IdentityServerUnavailable as exc:
            log_event(
                logger,
                logging.WARNING,
                "remote_login_failed",
                email=mask_email(email),
                reason="unavailable",
                error=str(exc),
            )
            raise ValueError("Invalid email or password")

        if not remote_identity.is_confirmed:
            raise ValueError("Email not confirmed")

        user = await self._provision_external_user.execute(remote_identity, password)
        await self._repo.update_last_login(user.id)
        refreshed_user = await self._repo.get_by_id(user.id)
        if refreshed_user:
            user = refreshed_user
        log_event(
            logger,
            logging.INFO,
            "remote_login_completed",
            user_id=user.id,
            email=mask_email(user.email),
        )
        return await self._issue_tokens(user)

    async def _issue_tokens(self, user: User) -> LoginResult:
        roles = user.roles or []
        access_token = self._token_service.create_access_token(user.id, roles)
        raw_refresh = self._token_service.create_refresh_token(user.id)
        new_hash = self._password_hasher.hash_token(raw_refresh)
        exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        await self._repo.store_refresh_token(user.id, new_hash, exp)

        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh,
            user=UserDTO.from_user(user, avatar_url=avatar_url),
        )
