from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteIdentity:
    external_user_id: str
    email: str
    full_name: str
    slug: str | None
    is_admin: bool
    is_confirmed: bool
