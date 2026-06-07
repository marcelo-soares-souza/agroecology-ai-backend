from __future__ import annotations

from src.domain.ports.user_repository import UserRepository


class GetUserBySlug:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, slug_or_id: str) -> dict | None:
        user = await self._repo.get_by_slug(slug_or_id)
        if not user:
            user = await self._repo.get_by_id(slug_or_id)
        if not user:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "slug": user.slug,
            "locale": user.locale,
            "roles": user.roles or [],
            "email_confirmed_at": user.email_confirmed_at.isoformat()
            if user.email_confirmed_at
            else None,
            "last_login_at": user.last_login_at.isoformat()
            if user.last_login_at
            else None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
