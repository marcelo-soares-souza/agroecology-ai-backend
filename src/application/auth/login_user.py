from __future__ import annotations

import logging

from src.application.auth.issue_auth_tokens import IssueAuthTokens
from src.application.auth.provision_external_user import ProvisionExternalUser
from src.domain.dto.auth_result import LoginResult
from src.domain.models.user import User
from src.domain.ports.auth_services_port import PasswordHasherPort
from src.domain.ports.identity_server_client import (
    IdentityServerClient,
    IdentityServerEmailNotConfirmed,
    IdentityServerInvalidCredentials,
    IdentityServerUnavailable,
)
from src.domain.ports.user_repository import UserRepository
from src.shared.email_utils import normalize_email
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")


class LoginUser:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        token_issuer: IssueAuthTokens,
        identity_client: IdentityServerClient | None = None,
        provision_external_user: ProvisionExternalUser | None = None,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer
        self._identity_client = identity_client
        self._provision_external_user = provision_external_user

    async def execute(self, email: str, password: str) -> LoginResult:
        email = normalize_email(email)
        user = await self._repo.get_by_email(email)
        if not user:
            return await self._login_with_external_identity(email, password)

        if user.password_hash is None:
            raise ValueError(
                "This account uses ORCID sign-in. Continue with ORCID or set a local password first."
            )

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

        self._ensure_required_consents(user)
        await self._repo.update_last_login(user.id)

        log_event(logger, logging.INFO, "local_login_completed", user_id=user.id)
        return await self._token_issuer.execute(user)

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
            raise ValueError("Email not confirmed") from None
        except IdentityServerInvalidCredentials:
            log_event(
                logger,
                logging.WARNING,
                "remote_login_failed",
                email=mask_email(email),
                reason="invalid_credentials",
            )
            raise ValueError("Invalid email or password") from None
        except IdentityServerUnavailable as exc:
            log_event(
                logger,
                logging.WARNING,
                "remote_login_failed",
                email=mask_email(email),
                reason="unavailable",
                error=str(exc),
            )
            raise ValueError("Invalid email or password") from exc

        if not remote_identity.is_confirmed:
            raise ValueError("Email not confirmed")

        user = await self._provision_external_user.execute(remote_identity, password)
        await self._repo.update_last_login(user.id)
        refreshed_user = await self._repo.get_by_id(user.id)
        if refreshed_user:
            user = refreshed_user
        self._ensure_required_consents(user)
        log_event(
            logger,
            logging.INFO,
            "remote_login_completed",
            user_id=user.id,
            email=mask_email(user.email),
        )
        return await self._token_issuer.execute(user)

    @staticmethod
    def _ensure_required_consents(user: User) -> None:
        if not user.privacy_policy_accepted or not user.tos_accepted:
            raise ValueError("Privacy policy and terms must be accepted")
