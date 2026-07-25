from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OAuthLoginState:
    id: str
    provider: str
    state_hash: str
    nonce_hash: str | None
    return_to: str | None
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime
