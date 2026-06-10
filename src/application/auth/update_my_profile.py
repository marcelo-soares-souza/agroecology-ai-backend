from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class UpdateMyProfile:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(
        self,
        user_id: str,
        full_name: str | None = None,
        email: str | None = None,
        about: str | None = None,
        link: str | None = None,
    ) -> UserDTO | None:
        updates: dict[str, str | None] = {}

        if about is not None:
            if len(about) > 4096:
                raise ValueError("About must not exceed 4096 characters")
            updates["about"] = about or None

        if link is not None:
            if link and not link.startswith(("http://", "https://")):
                raise ValueError("Link must start with http:// or https://")
            if link and len(link) > 2000:
                raise ValueError("Link must not exceed 2000 characters")
            updates["link"] = link or None

        if full_name is not None:
            updates["full_name"] = full_name

        if email is not None:
            updates["email"] = email

        if not updates:
            user = await self._user_repo.get_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            avatar_url = (
                f"/api/v1/users/{user.slug}/profile/avatar/file"
                if user.avatar_path
                else None
            )
            return UserDTO.from_user(user, avatar_url=avatar_url)

        updated = await self._user_repo.update(user_id, **updates)
        if not updated:
            raise ValueError("User not found")
        avatar_url = (
            f"/api/v1/users/{updated.slug}/profile/avatar/file"
            if updated.avatar_path
            else None
        )
        return UserDTO.from_user(updated, avatar_url=avatar_url)
