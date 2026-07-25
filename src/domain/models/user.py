from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """A registered user account.

    Attributes:
        id: Unique user identifier.
        email: The user's email address.
        full_name: The user's full display name.
        status: The account status.
        slug: The URL-friendly identifier.
        locale: The user's preferred locale.
        password_hash: The stored password hash.
        created_at: Timestamp of account creation.
        updated_at: Timestamp of last update.
        email_confirmed_at: Timestamp of email confirmation.
        last_login_at: Timestamp of last login.
        roles: List of role keys (populated on login).
        about: User's self-description.
        link: User's external link.
        avatar_path: Server-side path to the avatar file.
        approved_suggestions_count: Number of suggestions approved.
    """

    id: str
    email: str
    full_name: str
    status: str
    slug: str
    locale: str
    password_hash: str | None
    created_at: datetime
    updated_at: datetime
    email_confirmed_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str] | None = None  # populated on login/me
    about: str | None = None
    link: str | None = None
    avatar_path: str | None = None
    approved_suggestions_count: int = 0
    privacy_policy_accepted: bool = False
    privacy_policy_accepted_at: datetime | None = None
    privacy_policy_version: str | None = None
    tos_accepted: bool = False
    tos_accepted_at: datetime | None = None
    tos_version: str | None = None
    deleted_at: datetime | None = None
    erased_at: datetime | None = None
    erasure_status: str = "none"
    primary_auth_provider: str | None = None
