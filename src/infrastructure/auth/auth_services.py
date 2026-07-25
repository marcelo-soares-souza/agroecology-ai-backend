from __future__ import annotations

from src.domain.ports.auth_services_port import (
    EmailPort,
    HumanCheckPort,
    PasswordHasherPort,
    TokenServicePort,
)
from src.domain.dto.auth_result import ChallengeResult, TokenPayload
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

    def decode(self, token: str) -> TokenPayload | None:
        try:
            payload = jwt_handler.decode_token(token)
        except Exception:
            return None
        return TokenPayload(
            subject=payload.get("sub"),
            roles=list(payload.get("roles") or []),
            issued_at=payload.get("iat"),
            expires_at=payload.get("exp"),
            token_id=payload.get("jti"),
        )


class JwtHumanCheck(HumanCheckPort):
    def create_challenge(self, locale: str = "pt-BR") -> ChallengeResult:
        challenge = human_check.create_challenge(locale)
        return ChallengeResult(
            challenge_id=challenge["challenge_id"],
            question=challenge["question"],
        )

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

    async def send_suggestion_submitted_notification(
        self, admin_email: str, submitter_name: str, submitter_email: str, title: str
    ) -> bool:
        return await smtp_service.send_suggestion_submitted_email(
            admin_email, submitter_name, submitter_email, title
        )

    async def send_suggestion_approved_notification(
        self, user_email: str, title: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_suggestion_approved_email(
            user_email, title, locale
        )

    async def send_suggestion_rejected_notification(
        self, user_email: str, title: str, admin_comment: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_suggestion_rejected_email(
            user_email, title, admin_comment, locale
        )

    async def send_delete_account_confirmation(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_delete_account_confirmation_email(
            to_email, token, locale
        )

    async def send_orcid_link_confirmation(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        return await smtp_service.send_orcid_link_confirmation_email(
            to_email, token, locale
        )
