from __future__ import annotations

from pathlib import Path

from src.domain.dto.user_dto import UserDTO


class GetAvatarFile:
    async def execute(self, user: UserDTO) -> str | None:
        if not user.avatar_path:
            return None
        path = Path(user.avatar_path)
        if not path.exists():
            return None
        return str(path)
