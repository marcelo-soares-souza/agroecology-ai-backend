from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.dto.auth_result import LoginResult
from src.domain.dto.user_dto import UserDTO
from src.domain.ports.auth_services_port import PasswordHasherPort, TokenServicePort
from src.domain.ports.user_repository import UserRepository
from src.shared.config import REFRESH_TOKEN_TTL_DAYS


class RefreshToken:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def execute(self, refresh_token: str) -> LoginResult:
        token_hash = self._password_hasher.hash_token(refresh_token)
        stored = await self._repo.get_refresh_token(token_hash)

        if not stored:
            raise ValueError("Invalid refresh token")

        if stored["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Refresh token expired")

        if stored.get("revoked_at"):
            await self._repo.revoke_all_refresh_tokens(stored["user_id"])
            raise ValueError("Token reuse detected")

        await self._repo.revoke_refresh_token(token_hash)

        user = await self._repo.get_by_id(stored["user_id"])
        if not user or user.status != "active":
            raise ValueError("Account not active")

        roles = user.roles or []
        access_token = self._token_service.create_access_token(user.id, roles)
        raw_refresh = self._token_service.create_refresh_token(user.id)
        new_hash = self._password_hasher.hash_token(raw_refresh)
        exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        await self._repo.store_refresh_token(user.id, new_hash, exp)

        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh,
            user=UserDTO.minimal(user),
        )
