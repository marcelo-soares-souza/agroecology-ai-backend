from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
)
from src.infrastructure.auth.password_hasher import hash_token
from src.shared.config import REFRESH_TOKEN_TTL_DAYS


class RefreshToken:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, refresh_token: str) -> dict:
        token_hash = hash_token(refresh_token)
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
        access_token = create_access_token(user.id, roles)
        raw_refresh = create_refresh_token(user.id)
        new_hash = hash_token(raw_refresh)
        exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        await self._repo.store_refresh_token(user.id, new_hash, exp)

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "slug": user.slug,
                "locale": user.locale,
                "roles": roles,
            },
        }
