from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.user import User


class UserRepository(ABC):
    """Persistence interface for user accounts and authentication tokens.

    Manages user CRUD, email confirmation tokens, refresh tokens,
    and role assignments.
    """

    @abstractmethod
    async def create(
        self,
        email: str,
        full_name: str,
        password_hash: str,
        slug: str,
        locale: str,
        role_key: str,
        privacy_policy_accepted: bool = False,
        tos_accepted: bool = False,
    ) -> User:
        """Create a new user account.

        Args:
            email: The user's email address.
            full_name: The user's full name.
            password_hash: The hashed password.
            slug: The URL-friendly identifier for the user.
            locale: The user's preferred locale.
            role_key: The initial role to assign.
            privacy_policy_accepted: Whether the privacy policy was accepted.
            tos_accepted: Whether the terms of service were accepted.

        Returns:
            The newly created user.
        """

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        """Retrieve a user by their ID.

        Args:
            user_id: The user's unique identifier.

        Returns:
            The user, or None if not found.
        """

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address.

        Args:
            email: The user's email address.

        Returns:
            The user, or None if not found.
        """

    @abstractmethod
    async def get_by_slug(self, slug: str) -> User | None:
        """Retrieve a user by their URL slug.

        Args:
            slug: The user's slug.

        Returns:
            The user, or None if not found.
        """

    @abstractmethod
    async def list_all(self) -> list[User]:
        """List all registered users.

        Returns:
            A list of all users.
        """

    @abstractmethod
    async def list_active(self) -> list[User]:
        """List all active users.

        Returns:
            A list of users with active status.
        """

    @abstractmethod
    async def update(self, user_id: str, **kwargs) -> User | None:
        """Update arbitrary fields on a user.

        Args:
            user_id: The user's identifier.
            **kwargs: The fields to update.

        Returns:
            The updated user, or None if not found.
        """

    @abstractmethod
    async def delete(self, user_id: str) -> User | None:
        """Delete a user by ID.

        Args:
            user_id: The user's identifier.

        Returns:
            The deleted user, or None if not found.
        """

    @abstractmethod
    async def anonymize_user(self, user_id: str) -> User | None:
        """Anonymize personal data and mark user as deleted.

        Replaces name, email, about, link with placeholder values,
        deletes avatar, marks status as 'deleted', and revokes all tokens.

        Args:
            user_id: The user's identifier.

        Returns:
            The anonymized user, or None if not found.
        """

    @abstractmethod
    async def confirm_email(self, user_id: str) -> None:
        """Mark a user's email as confirmed.

        Args:
            user_id: The user's identifier.
        """

    @abstractmethod
    async def update_last_login(self, user_id: str) -> None:
        """Record the current timestamp as the user's last login.

        Args:
            user_id: The user's identifier.
        """

    @abstractmethod
    async def create_confirmation(
        self,
        user_id: str,
        token_hash: str,
        expires_at,
        purpose: str = "email_confirmation",
    ) -> None:
        """Store a confirmation token for a user.

        Args:
            user_id: The user's identifier.
            token_hash: The hashed token.
            expires_at: The token's expiration timestamp.
            purpose: The purpose of the token (e.g., email_confirmation).
        """

    @abstractmethod
    async def get_confirmation(
        self, token_hash: str, purpose: str = "email_confirmation"
    ) -> dict | None:
        """Retrieve a confirmation record by token hash.

        Args:
            token_hash: The hashed token.
            purpose: The token's purpose.

        Returns:
            The confirmation record as a dict, or None if not found or expired.
        """

    @abstractmethod
    async def mark_confirmation_done(self, confirmation_id: str) -> None:
        """Mark a confirmation token as used.

        Args:
            confirmation_id: The confirmation record's identifier.
        """

    @abstractmethod
    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at
    ) -> str:
        """Store a refresh token for a user.

        Args:
            user_id: The user's identifier.
            token_hash: The hashed refresh token.
            expires_at: The token's expiration timestamp.

        Returns:
            The stored token record ID.
        """

    @abstractmethod
    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a single refresh token.

        Args:
            token_hash: The hashed refresh token.
        """

    @abstractmethod
    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user.

        Args:
            user_id: The user's identifier.
        """

    @abstractmethod
    async def get_refresh_token(self, token_hash: str) -> dict | None:
        """Retrieve a refresh token record.

        Args:
            token_hash: The hashed refresh token.

        Returns:
            The token record as a dict, or None if not found or revoked.
        """

    @abstractmethod
    async def assign_role(self, user_id: str, role_key: str) -> None:
        """Assign a role to a user.

        Args:
            user_id: The user's identifier.
            role_key: The role key to assign.
        """
