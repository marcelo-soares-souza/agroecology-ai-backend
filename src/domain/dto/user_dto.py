from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.user import User


@dataclass
class UserDTO:
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

    @staticmethod
    def from_user(user: User, include_timestamps: bool = True) -> UserDTO:
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
            avatar_url=f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None,
            avatar_path=user.avatar_path,
        )
        if include_timestamps:
            dto.created_at = user.created_at.isoformat()
            dto.updated_at = user.updated_at.isoformat()
        return dto

    @staticmethod
    def minimal(user: User) -> UserDTO:
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
            avatar_url=f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None,
            avatar_path=user.avatar_path,
        )
