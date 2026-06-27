from __future__ import annotations

from dataclasses import dataclass

from src.domain.dto.user_dto import UserDTO


@dataclass
class LoginResult:
    """Result of a successful login.

    Attributes:
        access_token: The JWT access token.
        refresh_token: The refresh token.
        user: The authenticated user's DTO.
    """

    access_token: str
    refresh_token: str
    user: UserDTO


@dataclass(frozen=True)
class ChallengeResult:
    """A human-verification challenge.

    Attributes:
        challenge_id: The challenge's unique identifier.
        question: The challenge question text.
    """

    challenge_id: str
    question: str


@dataclass(frozen=True)
class TokenPayload:
    """Decoded access token payload used by application services."""

    subject: str | None
    roles: list[str]
    issued_at: int | None = None
    expires_at: int | None = None
    token_id: str | None = None
