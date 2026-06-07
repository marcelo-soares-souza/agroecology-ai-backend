from __future__ import annotations

from src.domain.dto.auth_result import ChallengeResult
from src.domain.ports.auth_services_port import HumanCheckPort


class GetHumanChallenge:
    def __init__(self, human_check: HumanCheckPort) -> None:
        self._human_check = human_check

    def execute(self, locale: str = "pt-BR") -> ChallengeResult:
        challenge = self._human_check.create_challenge(locale=locale)
        return ChallengeResult(
            challenge_id=challenge["challenge_id"],
            question=challenge["question"],
        )
