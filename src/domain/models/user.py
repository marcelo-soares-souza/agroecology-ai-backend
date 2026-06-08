from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    email: str
    full_name: str
    status: str
    slug: str
    locale: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
    email_confirmed_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str] | None = None  # populated on login/me
    about: str | None = None
    link: str | None = None
