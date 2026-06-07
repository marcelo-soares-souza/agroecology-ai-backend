from __future__ import annotations

from dataclasses import dataclass

from src.domain.dto.user_dto import UserDTO


@dataclass
class LoginResult:
    access_token: str
    refresh_token: str
    user: UserDTO


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    question: str
