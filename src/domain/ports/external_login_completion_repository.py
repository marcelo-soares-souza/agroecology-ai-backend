from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.external_login_completion import ExternalLoginCompletion


class ExternalLoginCompletionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        provider: str,
        external_user_id: str,
        external_slug: str | None,
        display_name: str | None,
        email: str | None,
        user_id: str | None,
        token_hash: str,
        status: str,
        expires_at,
    ) -> ExternalLoginCompletion:
        pass

    @abstractmethod
    async def get_by_token_hash(
        self, token_hash: str
    ) -> ExternalLoginCompletion | None:
        pass

    @abstractmethod
    async def consume(self, completion_id: str) -> None:
        pass
