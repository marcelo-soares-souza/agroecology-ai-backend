from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.ports.user_repository import UserRepository
from src.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
)
from src.infrastructure.auth.password_hasher import (
    hash_token,
    verify_password,
)
from src.shared.config import REFRESH_TOKEN_TTL_DAYS


class LoginUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, email: str, password: str) -> dict:
        user = await self._repo.get_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if user.email_confirmed_at is None:
            raise ValueError("Email not confirmed")

        if user.status != "active":
            raise ValueError("Account is not active")

        await self._repo.update_last_login(user.id)

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
                "email_confirmed_at": user.email_confirmed_at.isoformat()
                if user.email_confirmed_at
                else None,
                "last_login_at": user.last_login_at.isoformat()
                if user.last_login_at
                else None,
                "created_at": user.created_at.isoformat(),
            },
        }
