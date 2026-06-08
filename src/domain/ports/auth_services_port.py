from abc import ABC, abstractmethod


class PasswordHasherPort(ABC):
    @abstractmethod
    def hash_password(self, password: str) -> str: ...

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool: ...

    @abstractmethod
    def generate_token(self, length: int = 32) -> str: ...

    @abstractmethod
    def hash_token(self, token: str) -> str: ...


class TokenServicePort(ABC):
    @abstractmethod
    def create_access_token(self, user_id: str, roles: list[str]) -> str: ...

    @abstractmethod
    def create_refresh_token(self, user_id: str) -> str: ...


class HumanCheckPort(ABC):
    @abstractmethod
    def create_challenge(self, locale: str = "pt-BR") -> dict[str, str]: ...

    @abstractmethod
    def verify_challenge(self, challenge_id: str, answer: str) -> bool: ...


class EmailPort(ABC):
    @abstractmethod
    async def send_confirmation_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool: ...

    @abstractmethod
    async def send_reset_email(
        self, to_email: str, token: str, locale: str = "pt-BR"
    ) -> bool: ...

    @abstractmethod
    async def send_admin_new_user_notification(
        self, user_email: str, user_name: str, locale: str = "pt-BR"
    ) -> bool: ...

    @abstractmethod
    async def send_suggestion_submitted_notification(
        self, admin_email: str, submitter_name: str, submitter_email: str, title: str
    ) -> bool: ...

    @abstractmethod
    async def send_suggestion_approved_notification(
        self, user_email: str, title: str, locale: str = "pt-BR"
    ) -> bool: ...

    @abstractmethod
    async def send_suggestion_rejected_notification(
        self, user_email: str, title: str, admin_comment: str, locale: str = "pt-BR"
    ) -> bool: ...
