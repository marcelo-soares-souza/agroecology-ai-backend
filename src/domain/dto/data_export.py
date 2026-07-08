from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExportedUserData:
    id: str
    email: str
    full_name: str
    slug: str
    locale: str
    status: str
    about: str | None
    link: str | None
    created_at: str | None
    updated_at: str | None
    email_confirmed_at: str | None
    last_login_at: str | None
    roles: list[str] | None
    approved_suggestions_count: int
    privacy_policy_accepted: bool
    privacy_policy_accepted_at: str | None
    privacy_policy_version: str | None
    tos_accepted: bool
    tos_accepted_at: str | None
    tos_version: str | None
    deleted_at: str | None
    erased_at: str | None
    erasure_status: str


@dataclass(frozen=True)
class ExportedSuggestionData:
    id: str
    status: str
    title: str | None
    authors: str | None
    url: str | None
    user_comment: str
    admin_comment: str | None
    original_filename: str | None
    file_type: str | None
    file_size: int | None
    document_id: str | None
    reviewed_by: str | None
    reviewed_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ExportedExternalIdentityData:
    id: str
    provider: str
    external_user_id: str
    external_email: str | None
    external_slug: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None


@dataclass(frozen=True)
class ExportedChatMessageData:
    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    task_id: str | None
    sources: list[dict] | None
    error: str | None
    duration_ms: int | None
    created_at: str


@dataclass(frozen=True)
class ExportedChatConversationData:
    id: str
    title: str
    status: str
    message_count: int
    last_message_preview: str | None
    created_at: str
    updated_at: str
    last_message_at: str
    deleted_at: str | None
    messages: list[ExportedChatMessageData]


@dataclass(frozen=True)
class PersonalDataExport:
    user: ExportedUserData
    suggestions: list[ExportedSuggestionData]
    external_identities: list[ExportedExternalIdentityData]
    chat_conversations: list[ExportedChatConversationData]

    def to_dict(self) -> dict:
        return asdict(self)
