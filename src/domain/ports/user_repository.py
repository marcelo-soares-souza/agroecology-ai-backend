from abc import ABC, abstractmethod

from src.domain.models.user import User


class UserRepository(ABC):
    @abstractmethod
    async def create(
        self,
        email: str,
        full_name: str,
        password_hash: str,
        slug: str,
        locale: str,
        role_key: str,
    ) -> User: ...

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> User | None: ...

    @abstractmethod
    async def list_all(self) -> list[User]: ...

    @abstractmethod
    async def list_active(self) -> list[User]: ...

    @abstractmethod
    async def update(self, user_id: str, **kwargs) -> User | None: ...

    @abstractmethod
    async def delete(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def confirm_email(self, user_id: str) -> None: ...

    @abstractmethod
    async def update_last_login(self, user_id: str) -> None: ...

    @abstractmethod
    async def create_confirmation(
        self,
        user_id: str,
        token_hash: str,
        expires_at,
        purpose: str = "email_confirmation",
    ) -> None: ...

    @abstractmethod
    async def get_confirmation(
        self, token_hash: str, purpose: str = "email_confirmation"
    ) -> dict | None: ...

    @abstractmethod
    async def mark_confirmation_done(self, confirmation_id: str) -> None: ...

    @abstractmethod
    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at
    ) -> str: ...

    @abstractmethod
    async def revoke_refresh_token(self, token_hash: str) -> None: ...

    @abstractmethod
    async def revoke_all_refresh_tokens(self, user_id: str) -> None: ...

    @abstractmethod
    async def get_refresh_token(self, token_hash: str) -> dict | None: ...

    @abstractmethod
    async def assign_role(self, user_id: str, role_key: str) -> None: ...
