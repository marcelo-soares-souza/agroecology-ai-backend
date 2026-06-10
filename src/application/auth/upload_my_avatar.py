from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.domain.dto.user_dto import UserDTO
from src.domain.ports.user_repository import UserRepository

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


class UploadMyAvatar:
    def __init__(
        self,
        user_repo: UserRepository,
        avatar_dir: Path,
        process_avatar: Callable[[bytes], bytes],
    ) -> None:
        self._user_repo = user_repo
        self._avatar_dir = avatar_dir
        self._process_avatar = process_avatar

    async def execute(
        self,
        user_id: str,
        content: bytes,
        content_type: str,
    ) -> UserDTO:
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError("Unsupported image type. Use JPEG, PNG, or WebP.")

        if len(content) > MAX_AVATAR_SIZE:
            raise ValueError("Image must not exceed 5MB.")

        try:
            processed = self._process_avatar(content)
        except Exception as e:
            raise ValueError(f"Invalid image: {e}")

        user_dir = self._avatar_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = user_dir / "avatar.webp"
        avatar_path.write_bytes(processed)

        updated = await self._user_repo.update(user_id, avatar_path=str(avatar_path))
        if not updated:
            raise ValueError("User not found")
        avatar_url = (
            f"/api/v1/users/{updated.slug}/profile/avatar/file"
            if updated.avatar_path
            else None
        )
        return UserDTO.from_user(updated, avatar_url=avatar_url)
