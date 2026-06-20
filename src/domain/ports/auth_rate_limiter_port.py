from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.domain.dto.auth_rate_limit import AuthRateLimitBlock


class AuthRateLimiterPort(ABC):
    """Port for tracking failed public authentication attempts."""

    @abstractmethod
    def get_block(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        """Return an active block for any identifier, if present."""

    @abstractmethod
    def record_failure(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        """Record a failed attempt and return a block when the limit is reached."""

    @abstractmethod
    def reset(self, action: str, identifiers: Sequence[str]) -> None:
        """Clear failed-attempt counters for the given identifiers."""
