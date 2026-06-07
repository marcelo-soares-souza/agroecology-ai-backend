from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.dto.auth_result import LoginResult
from src.domain.dto.user_dto import UserDTO
from src.domain.ports.auth_services_port import PasswordHasherPort, TokenServicePort
from src.domain.ports.user_repository import UserRepository
from src.shared.config import REFRESH_TOKEN_TTL_DAYS


class LoginUser:
    def __init__(
        self,
        repo: UserRepository,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self._repo = repo
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def execute(self, email: str, password: str) -> LoginResult:
        user = await self._repo.get_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")

        if not self._password_hasher.verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if user.email_confirmed_at is None:
            raise ValueError("Email not confirmed")

        if user.status != "active":
            raise ValueError("Account is not active")

        await self._repo.update_last_login(user.id)

        roles = user.roles or []
        access_token = self._token_service.create_access_token(user.id, roles)
        raw_refresh = self._token_service.create_refresh_token(user.id)
        new_hash = self._password_hasher.hash_token(raw_refresh)
        exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        await self._repo.store_refresh_token(user.id, new_hash, exp)

        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh,
            user=UserDTO.from_user(user),
        )
