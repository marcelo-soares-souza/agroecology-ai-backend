from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.chat_message import ChatMessage
from src.domain.models.chat_conversation import (
    ChatConversationDetail,
    ChatConversationMessage,
    ChatConversationSummary,
)


class ChatConversationRepository(ABC):
    @abstractmethod
    async def list_for_user(
        self, user_id: str, limit: int, offset: int
    ) -> tuple[list[ChatConversationSummary], int]:
        """List active conversations owned by a user."""

    @abstractmethod
    async def get_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationDetail | None:
        """Load a conversation and all messages scoped to the owner."""

    @abstractmethod
    async def get_summary_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationSummary | None:
        """Load a conversation summary scoped to the owner."""

    @abstractmethod
    async def create(self, user_id: str, title: str) -> ChatConversationSummary:
        """Create a new active conversation for a user."""

    @abstractmethod
    async def rename(
        self, conversation_id: str, user_id: str, title: str
    ) -> ChatConversationSummary | None:
        """Rename an active conversation owned by a user."""

    @abstractmethod
    async def soft_delete(self, conversation_id: str, user_id: str) -> bool:
        """Mark a conversation as deleted for its owner."""

    @abstractmethod
    async def append_user_message(
        self, conversation_id: str, user_id: str, content: str
    ) -> ChatConversationMessage:
        """Append a completed user message."""

    @abstractmethod
    async def append_assistant_placeholder(
        self, conversation_id: str, user_id: str, task_id: str
    ) -> ChatConversationMessage:
        """Append a pending assistant message linked to an answer task."""

    @abstractmethod
    async def complete_assistant_message(
        self,
        message_id: str,
        user_id: str,
        content: str,
        sources: list[dict],
        duration_ms: int,
    ) -> ChatConversationMessage | None:
        """Store a completed assistant answer."""

    @abstractmethod
    async def fail_assistant_message(
        self, message_id: str, user_id: str, error: str
    ) -> ChatConversationMessage | None:
        """Store an assistant task failure."""

    @abstractmethod
    async def get_recent_history(
        self,
        conversation_id: str,
        user_id: str,
        max_messages: int,
        max_message_chars: int,
        max_total_chars: int,
    ) -> list[ChatMessage]:
        """Load recent completed messages for RAG follow-up context."""

    @abstractmethod
    async def delete_for_user(self, user_id: str) -> None:
        """Delete all conversations for a user."""
