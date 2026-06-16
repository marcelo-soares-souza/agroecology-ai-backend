from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExternalIdentity:
    id: str
    user_id: str
    provider: str
    external_user_id: str
    external_email: str
    external_slug: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
