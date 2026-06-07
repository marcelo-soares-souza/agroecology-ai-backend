from __future__ import annotations

from src.domain.ports.user_repository import UserRepository


class ListUsers:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[dict]:
        users = await self._repo.list_all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "status": u.status,
                "slug": u.slug,
                "locale": u.locale,
                "roles": u.roles or [],
                "email_confirmed_at": u.email_confirmed_at.isoformat()
                if u.email_confirmed_at
                else None,
                "last_login_at": u.last_login_at.isoformat()
                if u.last_login_at
                else None,
                "created_at": u.created_at.isoformat(),
                "updated_at": u.updated_at.isoformat(),
            }
            for u in users
        ]
