from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatConversationSummary:
    id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    deleted_at: datetime | None = None
    message_count: int = 0
    last_message_preview: str | None = None


@dataclass
class ChatConversationMessage:
    id: str
    conversation_id: str
    user_id: str
    role: str
    content: str
    status: str
    created_at: datetime
    task_id: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class ChatConversationDetail:
    conversation: ChatConversationSummary
    messages: list[ChatConversationMessage]
