from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.config import AuthConfig
from src.domain.dto.auth_result import LoginResult
from src.domain.dto.user_dto import UserDTO
from src.domain.models.user import User
from src.domain.ports.auth_services_port import PasswordHasherPort, TokenServicePort
from src.domain.ports.user_repository import UserRepository


class IssueAuthTokens:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
        config: AuthConfig,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._config = config

    async def execute(self, user: User) -> LoginResult:
        roles = user.roles or []
        access_token = self._token_service.create_access_token(user.id, roles)
        raw_refresh = self._token_service.create_refresh_token(user.id)
        token_hash = self._password_hasher.hash_token(raw_refresh)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._config.refresh_token_ttl_days
        )
        await self._repo.store_refresh_token(user.id, token_hash, expires_at)

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
