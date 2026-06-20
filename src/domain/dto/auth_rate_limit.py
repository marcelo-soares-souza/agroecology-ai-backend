from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuthRateLimitBlock:
    """Represents an active authentication rate-limit block."""

    retry_after_seconds: int
    blocked_until: datetime
