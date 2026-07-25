from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from src.application.auth.issue_auth_tokens import IssueAuthTokens
from src.domain.dto.auth_result import LoginResult
from src.domain.dto.orcid_identity import OrcidIdentity
from src.domain.models.external_login_completion import ExternalLoginCompletion
from src.domain.models.user import User
from src.domain.ports.auth_services_port import EmailPort, PasswordHasherPort
from src.domain.ports.external_identity_repository import ExternalIdentityRepository
from src.domain.ports.external_login_completion_repository import (
    ExternalLoginCompletionRepository,
)
from src.domain.ports.oauth_state_repository import OAuthStateRepository
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.identity.orcid_oauth_client import (
    OrcidOAuthClient,
    OrcidOAuthError,
)
from src.shared.config import APP_URL, PRIVACY_POLICY_VERSION, TOS_VERSION
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.auth")

ORCID_PROVIDER = "orcid"


@dataclass(frozen=True)
class OrcidProviderStatus:
    enabled: bool


@dataclass(frozen=True)
class OrcidCallbackResult:
    redirect_url: str


@dataclass(frozen=True)
class OrcidCompletionResult:
    status: str
    message: str


class OrcidAuthService:
    def __init__(
        self,
        *,
        enabled: bool,
        client_id: str,
        redirect_uri: str,
        authorize_url: str,
        completion_ttl_minutes: int,
        oauth_state_repo: OAuthStateRepository,
        completion_repo: ExternalLoginCompletionRepository,
        external_identity_repo: ExternalIdentityRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasherPort,
        email_service: EmailPort,
        token_issuer: IssueAuthTokens,
        orcid_client: OrcidOAuthClient | None,
    ) -> None:
        self._enabled = enabled
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._authorize_url = authorize_url
        self._completion_ttl_minutes = completion_ttl_minutes
        self._oauth_state_repo = oauth_state_repo
        self._completion_repo = completion_repo
        self._external_identity_repo = external_identity_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._email_service = email_service
        self._token_issuer = token_issuer
        self._orcid_client = orcid_client

    def provider_status(self) -> OrcidProviderStatus:
        return OrcidProviderStatus(enabled=self._is_ready())

    async def start(self, return_to: str | None = None) -> str:
        self._ensure_ready()
        state = self._password_hasher.generate_token(32)
        nonce = self._password_hasher.generate_token(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await self._oauth_state_repo.create(
            provider=ORCID_PROVIDER,
            state_hash=self._password_hasher.hash_token(state),
            nonce_hash=self._password_hasher.hash_token(nonce),
            return_to=self._safe_return_to(return_to),
            expires_at=expires_at,
        )
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "scope": "openid",
            "redirect_uri": self._redirect_uri,
            "state": state,
            "nonce": nonce,
        }
        return f"{self._authorize_url}?{urlencode(params)}"

    async def handle_callback(self, code: str, state: str) -> OrcidCallbackResult:
        self._ensure_ready()
        assert self._orcid_client is not None
        oauth_state = await self._oauth_state_repo.consume(
            ORCID_PROVIDER,
            self._password_hasher.hash_token(state),
        )
        if oauth_state is None:
            raise ValueError("Invalid or expired ORCID login state")

        try:
            identity = await self._orcid_client.exchange_code(code)
        except OrcidOAuthError as exc:
            raise ValueError(str(exc)) from exc
        linked = await self._external_identity_repo.get_by_provider_user_id(
            ORCID_PROVIDER,
            identity.orcid_id,
        )
        if linked is not None:
            user = await self._user_repo.get_by_id(linked.user_id)
            if user is None:
                raise ValueError("Linked ORCID account user was not found")
            if user.status != "active" or user.email_confirmed_at is None:
                return OrcidCallbackResult(
                    self._frontend_callback_url(
                        {
                            "status": "email_confirmation_required",
                            "return_to": oauth_state.return_to or "/",
                        }
                    )
                )
            if not user.privacy_policy_accepted or not user.tos_accepted:
                raise ValueError("Privacy policy and terms must be accepted")
            auth_code = await self._create_auth_code(identity, user)
            return OrcidCallbackResult(
                self._frontend_callback_url(
                    {
                        "auth_code": auth_code,
                        "return_to": oauth_state.return_to or "/",
                    }
                )
            )

        completion_token = await self._create_profile_completion(identity)
        params = {
            "status": "profile_required" if identity.email else "email_required",
            "completion_token": completion_token,
            "orcid_id": identity.orcid_id,
            "return_to": oauth_state.return_to or "/",
        }
        if identity.email:
            params["email"] = identity.email
        if identity.name:
            params["full_name"] = identity.name
        return OrcidCallbackResult(self._frontend_callback_url(params))

    async def exchange_auth_code(self, auth_code: str) -> LoginResult:
        completion = await self._completion_repo.get_by_token_hash(
            self._password_hasher.hash_token(auth_code)
        )
        if completion is None or completion.status != "tokens_ready":
            raise ValueError("Invalid or expired ORCID authorization code")
        if not completion.user_id:
            raise ValueError("Invalid ORCID authorization code")

        user = await self._user_repo.get_by_id(completion.user_id)
        if user is None:
            raise ValueError("User not found")
        if user.status != "active" or user.email_confirmed_at is None:
            raise ValueError("Email confirmation is required")
        if not user.privacy_policy_accepted or not user.tos_accepted:
            raise ValueError("Privacy policy and terms must be accepted")

        await self._completion_repo.consume(completion.id)
        await self._user_repo.update_last_login(user.id)
        refreshed = await self._user_repo.get_by_id(user.id)
        return await self._token_issuer.execute(refreshed or user)

    async def complete_email(
        self,
        *,
        completion_token: str,
        email: str,
        full_name: str,
        locale: str,
        privacy_policy_accepted: bool,
        tos_accepted: bool,
    ) -> OrcidCompletionResult:
        completion = await self._completion_repo.get_by_token_hash(
            self._password_hasher.hash_token(completion_token)
        )
        if completion is None or completion.status != "profile_required":
            raise ValueError("Invalid or expired ORCID completion token")
        if not privacy_policy_accepted:
            raise ValueError("Privacy Policy must be accepted")
        if not tos_accepted:
            raise ValueError("Terms of Service must be accepted")

        clean_email = email.strip().lower()
        clean_name = " ".join(full_name.strip().split())
        if not clean_email or "@" not in clean_email:
            raise ValueError("A valid email is required")
        if not clean_name:
            clean_name = completion.display_name or clean_email.split("@", 1)[0]

        existing = await self._user_repo.get_by_email(clean_email)
        if existing is not None:
            existing = await self._apply_required_consents(existing)
            token = await self._create_link_confirmation(completion, existing)
            try:
                await self._email_service.send_orcid_link_confirmation(
                    existing.email,
                    token,
                    existing.locale or locale or "pt-BR",
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "orcid_link_confirmation_email_failed",
                    error=str(exc),
                    email=mask_email(existing.email),
                )
            await self._completion_repo.consume(completion.id)
            return OrcidCompletionResult(
                status="account_link_confirmation_required",
                message="Check your email to confirm linking this ORCID iD.",
            )

        user = await self._create_orcid_user(
            completion=completion,
            email=clean_email,
            full_name=clean_name,
            locale=locale or "pt-BR",
            privacy_policy_accepted=privacy_policy_accepted,
            tos_accepted=tos_accepted,
        )
        await self._external_identity_repo.upsert(
            user_id=user.id,
            provider=ORCID_PROVIDER,
            external_user_id=completion.external_user_id,
            external_email=clean_email,
            external_slug=completion.external_slug,
        )
        await self._send_confirmation_for_user(user)
        await self._completion_repo.consume(completion.id)
        return OrcidCompletionResult(
            status="email_confirmation_required",
            message="Check your email to confirm your account.",
        )

    async def confirm_link(self, token: str) -> OrcidCompletionResult:
        completion = await self._completion_repo.get_by_token_hash(
            self._password_hasher.hash_token(token)
        )
        if completion is None or completion.status != "link_confirmation":
            raise ValueError("Invalid or expired ORCID link token")
        if not completion.user_id:
            raise ValueError("Invalid ORCID link token")

        user = await self._user_repo.get_by_id(completion.user_id)
        if user is None:
            raise ValueError("User not found")
        await self._external_identity_repo.upsert(
            user_id=user.id,
            provider=ORCID_PROVIDER,
            external_user_id=completion.external_user_id,
            external_email=completion.email or user.email,
            external_slug=completion.external_slug,
        )
        await self._completion_repo.consume(completion.id)
        return OrcidCompletionResult(
            status="linked",
            message="ORCID account linked successfully. You can now sign in with ORCID.",
        )

    def _is_ready(self) -> bool:
        return bool(
            self._enabled
            and self._client_id
            and self._redirect_uri
            and self._authorize_url
            and self._orcid_client is not None
        )

    def _ensure_ready(self) -> None:
        if not self._is_ready():
            raise ValueError("ORCID sign-in is not configured")

    async def _create_auth_code(self, identity: OrcidIdentity, user: User) -> str:
        token = self._password_hasher.generate_token(32)
        await self._completion_repo.create(
            provider=ORCID_PROVIDER,
            external_user_id=identity.orcid_id,
            external_slug=identity.slug or identity.orcid_id,
            display_name=identity.name,
            email=identity.email or user.email,
            user_id=user.id,
            token_hash=self._password_hasher.hash_token(token),
            status="tokens_ready",
            expires_at=self._completion_expires_at(),
        )
        return token

    async def _create_profile_completion(self, identity: OrcidIdentity) -> str:
        token = self._password_hasher.generate_token(32)
        await self._completion_repo.create(
            provider=ORCID_PROVIDER,
            external_user_id=identity.orcid_id,
            external_slug=identity.slug or identity.orcid_id,
            display_name=identity.name,
            email=identity.email,
            user_id=None,
            token_hash=self._password_hasher.hash_token(token),
            status="profile_required",
            expires_at=self._completion_expires_at(),
        )
        return token

    async def _create_link_confirmation(
        self, completion: ExternalLoginCompletion, user: User
    ) -> str:
        token = self._password_hasher.generate_token(32)
        await self._completion_repo.create(
            provider=completion.provider,
            external_user_id=completion.external_user_id,
            external_slug=completion.external_slug,
            display_name=completion.display_name,
            email=user.email,
            user_id=user.id,
            token_hash=self._password_hasher.hash_token(token),
            status="link_confirmation",
            expires_at=self._completion_expires_at(),
        )
        return token

    async def _create_orcid_user(
        self,
        *,
        completion: ExternalLoginCompletion,
        email: str,
        full_name: str,
        locale: str,
        privacy_policy_accepted: bool,
        tos_accepted: bool,
    ) -> User:
        slug = await self._generate_slug(
            completion.external_slug or full_name or completion.external_user_id
        )
        return await self._user_repo.create(
            email=email,
            full_name=full_name,
            password_hash=None,
            slug=slug,
            locale=locale,
            role_key="user",
            privacy_policy_accepted=privacy_policy_accepted,
            tos_accepted=tos_accepted,
            primary_auth_provider=ORCID_PROVIDER,
        )

    async def _apply_required_consents(self, user: User) -> User:
        updates = {}
        now = datetime.now(timezone.utc)
        if not user.privacy_policy_accepted:
            updates.update(
                {
                    "privacy_policy_accepted": True,
                    "privacy_policy_accepted_at": now,
                    "privacy_policy_version": PRIVACY_POLICY_VERSION,
                }
            )
        if not user.tos_accepted:
            updates.update(
                {
                    "tos_accepted": True,
                    "tos_accepted_at": now,
                    "tos_version": TOS_VERSION,
                }
            )
        if not updates:
            return user
        updated = await self._user_repo.update(user.id, **updates)
        return updated or user

    async def _send_confirmation_for_user(self, user: User) -> None:
        token = self._password_hasher.generate_token()
        token_hash = self._password_hasher.hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await self._user_repo.create_confirmation(user.id, token_hash, expires_at)
        try:
            await self._email_service.send_confirmation_email(
                user.email, token, user.locale or "pt-BR"
            )
            await self._email_service.send_admin_new_user_notification(
                user.email, user.full_name, user.locale or "pt-BR"
            )
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "orcid_registration_email_failed",
                error=str(exc),
                email=mask_email(user.email),
            )

    async def _generate_slug(self, value: str) -> str:
        base = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode()
            .strip()
            .lower()
        )
        base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        if not base:
            base = "user"
        candidate = base[:100].strip("-") or "user"
        suffix = 1
        while await self._user_repo.get_by_slug(candidate) is not None:
            suffix_text = f"-{suffix}"
            candidate = f"{base[: 100 - len(suffix_text)].strip('-')}{suffix_text}"
            suffix += 1
        return candidate

    def _completion_expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            minutes=self._completion_ttl_minutes
        )

    @staticmethod
    def _safe_return_to(value: str | None) -> str:
        if not value:
            return "/"
        if not value.startswith("/") or value.startswith("//"):
            return "/"
        return value

    @staticmethod
    def _frontend_callback_url(params: dict[str, str]) -> str:
        return f"{APP_URL.rstrip('/')}/auth/orcid/callback?{urlencode(params)}"
