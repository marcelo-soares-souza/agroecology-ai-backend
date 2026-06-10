from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.user import User


@dataclass
class UserDTO:
    """Public-facing user representation with computed fields.

    Attributes:
        id: The user's unique identifier.
        email: The user's email address.
        full_name: The user's full display name.
        status: The account status.
        slug: The URL-friendly identifier.
        locale: The user's preferred locale.
        roles: The list of role keys assigned to the user.
        email_confirmed_at: ISO timestamp of email confirmation.
        last_login_at: ISO timestamp of last login.
        created_at: ISO timestamp of account creation.
        updated_at: ISO timestamp of last update.
        about: User's self-description.
        link: User's external link.
        avatar_url: URL for the user's avatar image.
        avatar_path: Server-side path to the avatar file.
        approved_suggestions_count: Number of suggestions approved.
    """

    id: str
    email: str
    full_name: str
    status: str
    slug: str
    locale: str
    roles: list[str]
    email_confirmed_at: str | None = None
    last_login_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    about: str | None = None
    link: str | None = None
    avatar_url: str | None = None
    avatar_path: str | None = None
    approved_suggestions_count: int = 0

    @staticmethod
    def from_user(
        user: User,
        include_timestamps: bool = True,
        avatar_url: str | None = None,
    ) -> UserDTO:
        dto = UserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            status=user.status,
            slug=user.slug,
            locale=user.locale,
            roles=user.roles or [],
            email_confirmed_at=user.email_confirmed_at.isoformat()
            if user.email_confirmed_at
            else None,
            last_login_at=user.last_login_at.isoformat()
            if user.last_login_at
            else None,
            about=user.about,
            link=user.link,
            avatar_url=avatar_url,
            avatar_path=user.avatar_path,
            approved_suggestions_count=user.approved_suggestions_count,
        )
        if include_timestamps:
            dto.created_at = user.created_at.isoformat()
            dto.updated_at = user.updated_at.isoformat()
        return dto

    @staticmethod
    def minimal(user: User, avatar_url: str | None = None) -> UserDTO:
        return UserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            status=user.status,
            slug=user.slug,
            locale=user.locale,
            roles=user.roles or [],
            about=user.about,
            link=user.link,
            avatar_url=avatar_url,
            avatar_path=user.avatar_path,
            approved_suggestions_count=user.approved_suggestions_count,
        )
