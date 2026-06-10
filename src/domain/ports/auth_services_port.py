from __future__ import annotations

from abc import ABC, abstractmethod


class PasswordHasherPort(ABC):
    """Port for password hashing and verification.

    Provides token generation and hashing for email confirmations
    and password reset flows.
    """

    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash a plain-text password.

        Args:
            password: The plain-text password.

        Returns:
            The hashed password.
        """

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a stored hash.

        Args:
            password: The plain-text password to verify.
            password_hash: The stored password hash.

        Returns:
            True if the password matches the hash.
        """

    @abstractmethod
    def generate_token(self, length: int = 32) -> str:
        """Generate a cryptographically random token.

        Args:
            length: The token length in characters.

        Returns:
            The generated token string.
        """

    @abstractmethod
    def hash_token(self, token: str) -> str:
        """Hash a token for secure storage.

        Args:
            token: The plain-text token.

        Returns:
            The hashed token.
        """


class TokenServicePort(ABC):
    """Port for JWT token creation and validation.

    Creates access and refresh tokens for authenticated users,
    and decodes/validates tokens for session verification.
    """

    @abstractmethod
    def create_access_token(self, user_id: str, roles: list[str]) -> str:
        """Create a short-lived JWT access token.

        Args:
            user_id: The user's unique identifier.
            roles: The user's role keys.

        Returns:
            The signed JWT access token.
        """

    @abstractmethod
    def create_refresh_token(self, user_id: str) -> str:
        """Create a long-lived refresh token.

        Args:
            user_id: The user's unique identifier.

        Returns:
            The signed refresh token.
        """

    @abstractmethod
    def decode(self, token: str) -> dict | None:
        """Decode and validate a JWT token.

        Args:
            token: The JWT token string.

        Returns:
            The decoded payload as a dict, or None if invalid/expired.
        """


class HumanCheckPort(ABC):
    """Port for CAPTCHA-like human verification challenges."""

    @abstractmethod
    def create_challenge(self, locale: str = "pt-BR") -> dict[str, str]:
        """Generate a new human-verification challenge.

        Args:
            locale: The locale for the challenge question.

        Returns:
            A dict with challenge_id and question keys.
        """

    @abstractmethod
    def verify_challenge(self, challenge_id: str, answer: str) -> bool:
        """Verify an answer to a challenge.

        Args:
            challenge_id: The challenge's unique identifier.
            answer: The user's answer.

        Returns:
            True if the answer is correct.
        """


class EmailPort(ABC):
    """Port for sending transactional emails."""

    @abstractmethod
    async def send_confirmation_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        """Send an email confirmation message.

        Args:
            to_email: The recipient's email address.
            token: The confirmation token.
            locale: The email language locale.

        Returns:
            True if the email was sent successfully.
        """

    @abstractmethod
    async def send_reset_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool:
        """Send a password reset email.

        Args:
            to_email: The recipient's email address.
            token: The reset token.
            locale: The email language locale.

        Returns:
            True if the email was sent successfully.
        """

    @abstractmethod
    async def send_admin_new_user_notification(
        self, user_email: str, user_name: str, locale: str = "pt-BR"
    ) -> bool:
        """Notify admins about a new user registration.

        Args:
            user_email: The new user's email address.
            user_name: The new user's full name.
            locale: The email language locale.

        Returns:
            True if the email was sent successfully.
        """

    @abstractmethod
    async def send_suggestion_submitted_notification(
        self, admin_email: str, submitter_name: str, submitter_email: str, title: str
    ) -> bool:
        """Notify admins about a new document suggestion.

        Args:
            admin_email: The admin recipient's email.
            submitter_name: The submitter's full name.
            submitter_email: The submitter's email address.
            title: The suggested document title.

        Returns:
            True if the email was sent successfully.
        """

    @abstractmethod
    async def send_suggestion_approved_notification(
        self, user_email: str, title: str, locale: str = "pt-BR"
    ) -> bool:
        """Notify a user that their suggestion was approved.

        Args:
            user_email: The submitter's email address.
            title: The document title.
            locale: The email language locale.

        Returns:
            True if the email was sent successfully.
        """

    @abstractmethod
    async def send_suggestion_rejected_notification(
        self, user_email: str, title: str, admin_comment: str, locale: str = "pt-BR"
    ) -> bool:
        """Notify a user that their suggestion was rejected.

        Args:
            user_email: The submitter's email address.
            title: The document title.
            admin_comment: The rejection reason.
            locale: The email language locale.

        Returns:
            True if the email was sent successfully.
        """
