from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.oauth_login_state import OAuthLoginState


class OAuthStateRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        provider: str,
        state_hash: str,
        nonce_hash: str | None,
        return_to: str | None,
        expires_at,
    ) -> OAuthLoginState:
        pass

    @abstractmethod
    async def consume(self, provider: str, state_hash: str) -> OAuthLoginState | None:
        pass
