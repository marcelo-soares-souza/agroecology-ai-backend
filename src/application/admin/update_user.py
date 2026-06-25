from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class UpdateUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        actor_user_id: str,
        user_id: str,
        full_name: str | None = None,
        email: str | None = None,
        status: str | None = None,
        locale: str | None = None,
        role_key: str | None = None,
    ) -> UserDTO | None:
        if status == "deleted":
            raise ValueError("Use the delete endpoint to anonymize an account")
        if status is not None and status not in {
            "pending",
            "active",
            "suspended",
        }:
            raise ValueError(f"Invalid status: {status}")
        if role_key is not None and role_key not in {"admin", "user"}:
            raise ValueError(f"Invalid role_key: {role_key}")
        if user_id == actor_user_id:
            if role_key is not None and role_key != "admin":
                raise ValueError("Cannot remove your own administrator role")
            if status is not None and status != "active":
                raise ValueError("Cannot change your own account status")

        kwargs = {}
        if full_name is not None:
            kwargs["full_name"] = full_name
        if email is not None:
            kwargs["email"] = email
        if status is not None:
            kwargs["status"] = status
        if locale is not None:
            kwargs["locale"] = locale

        user = await self._repo.update(user_id, **kwargs)
        if not user:
            return None

        if role_key is not None:
            await self._repo.assign_role(user_id, role_key)
            user = await self._repo.get_by_id(user_id)
            if not user:
                return None

        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        return UserDTO.from_user(user, avatar_url=avatar_url)
