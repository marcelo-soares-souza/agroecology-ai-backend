from __future__ import annotations

import logging

from src.domain.ports.user_repository import UserRepository

logger = logging.getLogger("agroecology.auth")


class ExportMyData:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, user_id: str) -> dict:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "slug": user.slug,
                "locale": user.locale,
                "status": user.status,
                "about": user.about,
                "link": user.link,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "email_confirmed_at": (
                    user.email_confirmed_at.isoformat()
                    if user.email_confirmed_at
                    else None
                ),
                "last_login_at": (
                    user.last_login_at.isoformat() if user.last_login_at else None
                ),
                "roles": user.roles,
                "approved_suggestions_count": user.approved_suggestions_count,
            },
            "suggestions": [],
        }
