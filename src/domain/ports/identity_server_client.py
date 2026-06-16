from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.remote_identity import RemoteIdentity


class IdentityServerUnavailable(Exception):
    pass


class IdentityServerInvalidCredentials(Exception):
    pass


class IdentityServerEmailNotConfirmed(Exception):
    pass


class IdentityServerClient(ABC):
    @abstractmethod
    async def authenticate(self, email: str, password: str) -> RemoteIdentity:
        pass
