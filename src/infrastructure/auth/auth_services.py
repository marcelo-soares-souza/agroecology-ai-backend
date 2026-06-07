from __future__ import annotations

from src.domain.ports.auth_services_port import (
    EmailPort,
    HumanCheckPort,
    PasswordHasherPort,
    TokenServicePort,
)
from src.infrastructure.auth import human_check, jwt_handler, password_hasher
from src.infrastructure.email import smtp_service


class BCryptPasswordHasher(PasswordHasherPort):
    def hash_password(self, password: str) -> str:
        return password_hasher.hash_password(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return password_hasher.verify_password(password, password_hash)

    def generate_token(self, length: int = 32) -> str:
        return password_hasher.generate_token(length)

    def hash_token(self, token: str) -> str:
        return password_hasher.hash_token(token)


class JwtTokenService(TokenServicePort):
    def create_access_token(self, user_id: str, roles: list[str]) -> str:
        return jwt_handler.create_access_token(user_id, roles)

    def create_refresh_token(self, user_id: str) -> str:
        return jwt_handler.create_refresh_token(user_id)


class JwtHumanCheck(HumanCheckPort):
    def create_challenge(self, locale: str = "pt-BR") -> dict[str, str]:
        return human_check.create_challenge(locale)

    def verify_challenge(self, challenge_id: str, answer: str) -> bool:
        return human_check.verify_challenge(challenge_id, answer)


class SmtpEmailService(EmailPort):
    async def send_confirmation_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_confirmation_email(to_email, token, locale)

    async def send_reset_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_reset_email(to_email, token, locale)

    async def send_admin_new_user_notification(
        self, user_email: str, user_name: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_admin_new_user_notification(
            user_email, user_name, locale
        )
