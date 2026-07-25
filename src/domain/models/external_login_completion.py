from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExternalLoginCompletion:
    id: str
    provider: str
    external_user_id: str
    external_slug: str | None
    display_name: str | None
    email: str | None
    user_id: str | None
    token_hash: str
    status: str
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime
