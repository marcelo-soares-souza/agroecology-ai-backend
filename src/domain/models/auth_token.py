from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConfirmationTokenRecord:
    id: str
    user_id: str
    expires_at: datetime
    purpose: str
    confirmed_at: datetime | None = None


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: str
    user_id: str
    expires_at: datetime
    revoked_at: datetime | None = None
