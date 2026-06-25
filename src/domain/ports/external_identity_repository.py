from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.external_identity import ExternalIdentity


class ExternalIdentityRepository(ABC):
    @abstractmethod
    async def get_by_provider_user_id(
        self, provider: str, external_user_id: str
    ) -> ExternalIdentity | None:
        pass

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[ExternalIdentity]:
        pass

    @abstractmethod
    async def upsert(
        self,
        *,
        user_id: str,
        provider: str,
        external_user_id: str,
        external_email: str,
        external_slug: str | None,
    ) -> ExternalIdentity:
        pass
