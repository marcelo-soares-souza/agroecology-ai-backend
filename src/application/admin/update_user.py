from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository


class UpdateUser:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        user_id: str,
        full_name: str | None = None,
        email: str | None = None,
        status: str | None = None,
        locale: str | None = None,
        role_key: str | None = None,
    ) -> UserDTO | None:
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

        return UserDTO.from_user(user)
