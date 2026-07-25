from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

MAX_HISTORY_REQUEST_MESSAGE_CHARS = 16000


class ChatMessageRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=40)
    content: str = Field(
        ...,
        min_length=1,
        max_length=MAX_HISTORY_REQUEST_MESSAGE_CHARS,
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)
    history: list[ChatMessageRequest] = Field(default_factory=list)
    conversation_id: str | None = Field(default=None, max_length=80)
    locale: str | None = Field(default=None, max_length=20)


class AskResponse(BaseModel):
    task_id: str
    status: str
    conversation_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None


class AnswerResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    conversation_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None


class ChatConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatConversationUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class ChatConversationSummaryResponse(BaseModel):
    id: str
    title: str
    status: str
    message_count: int
    last_message_preview: str | None = None
    created_at: str
    updated_at: str
    last_message_at: str


class ChatConversationMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    task_id: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    duration_ms: int | None = None
    created_at: str


class ChatConversationDetailResponse(BaseModel):
    conversation: ChatConversationSummaryResponse
    messages: list[ChatConversationMessageResponse]


class ChatConversationListResponse(BaseModel):
    data: list[ChatConversationSummaryResponse]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str


class IngestionRunSchema(BaseModel):
    id: str
    status: str
    phase: str = "processing"
    chunks_indexed: int = 0
    chunks_generated: int = 0
    documents_total: int = 0
    documents_processed: int = 0
    force: bool = False
    error: str | None = None
    started_at: str
    finished_at: str | None = None
    queued_at: str | None = None


class StatusResponse(BaseModel):
    index_ready: bool
    schema_mismatch: bool = False
    index_version: str = "0"
    ingest_status: str
    chunks_indexed: int
    active_tasks: int
    cache_enabled: bool
    cache_hits: int
    pending_docs: int = 0
    indexed_docs: int = 0
    total_docs: int = 0
    llm_model: str
    llm_provider: str
    llm_transport: str
    llm_think_enabled: bool
    embedding_model: str
    embedding_device: str
    similarity_top_k: int
    bm25_top_k: int
    hybrid_top_k: int
    reranker_enabled: bool
    reranker_model: str | None = None
    reranker_device: str | None = None
    rerank_top_k: int
    last_ingestion: IngestionRunSchema | None = None


class IngestResponse(BaseModel):
    run_id: str
    status: str


class IngestStatusResponse(BaseModel):
    status: str
    phase: str | None = None
    chunks_indexed: int | None = None
    chunks_generated: int | None = None
    documents_total: int | None = None
    documents_processed: int | None = None
    error: str | None = None
    run_id: str | None = None


class AcademicMetadataSchema(BaseModel):
    provider: str
    external_id: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    publisher: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    abstract: str | None = None
    source_url: str | None = None
    open_access_url: str | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[dict[str, Any]] | None = None
    license: list[dict[str, Any]] | dict[str, Any] | None = None
    funder: list[dict[str, Any]] | dict[str, Any] | None = None
    match_confidence: float | None = None
    title_score: float | None = None
    author_score: float | None = None
    extracted_at: str
    updated_at: str


class DocumentSkipped(BaseModel):
    filename: str
    reason: str


class DocumentRecord(BaseModel):
    id: str
    filename: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    file_type: str
    file_size: int
    directory: str
    ingested: bool = False
    full_file_available: bool = True
    created_at: str
    updated_at: str
    suggested_by_user_id: str | None = None
    suggested_by_user_name: str | None = None
    suggested_by_user_slug: str | None = None
    academic_metadata: AcademicMetadataSchema | None = None


class DocumentListResponse(BaseModel):
    data: list[DocumentRecord]
    total: int
    limit: int
    offset: int


class DocumentStatsResponse(BaseModel):
    total: int
    indexed: int
    metadata_total: int
    metadata_extracted: int


class DocumentUploaded(BaseModel):
    id: str
    filename: str
    directory: str
    size: int


class DocumentUploadResponse(BaseModel):
    uploaded: list[DocumentUploaded]
    skipped: list[DocumentSkipped]


class MetadataExtractionStatusResponse(BaseModel):
    pending: int = 0
    running: int = 0
    active: int = 0


class DocumentUpdateBody(BaseModel):
    title: str | None = None
    authors: str | None = None
    url: str | None = None


class AcademicMetadataExtractBody(BaseModel):
    delay_seconds: int | None = None
    force: bool | None = None


class AcademicMetadataRunStatusResponse(BaseModel):
    status: str
    run_id: str | None = None
    documents_total: int = 0
    documents_processed: int = 0
    documents_enriched: int = 0
    documents_skipped: int = 0
    documents_failed: int = 0
    documents_pending: int = 0
    documents_processed_total: int = 0
    documents_skipped_total: int = 0
    documents_failed_total: int = 0
    documents_with_full_metadata: int = 0
    documents_eligible_pending: int = 0
    delay_seconds: int = 60
    current_document_id: str | None = None
    error: str | None = None
    job_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AcademicMetadataExtractResponse(BaseModel):
    run_id: str
    status: str
    delay_seconds: int


# ── Auth ──────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=320)
    password: str = Field(
        ..., min_length=8, max_length=128, description="Minimum 8 characters"
    )
    challenge_id: str
    challenge_answer: str = Field(..., min_length=1, max_length=200)
    locale: str = Field(default="pt-BR")
    privacy_policy_accepted: bool = Field(..., description="Must be True")
    tos_accepted: bool = Field(..., description="Must be True")


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str


class ConfirmEmailRequest(BaseModel):
    token: str


class ResendConfirmationRequest(BaseModel):
    email: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthProvidersResponse(BaseModel):
    orcid_enabled: bool


class OrcidExchangeRequest(BaseModel):
    auth_code: str = Field(..., min_length=1, max_length=200)


class OrcidCompleteEmailRequest(BaseModel):
    completion_token: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=320)
    full_name: str = Field(..., min_length=1, max_length=200)
    locale: str = Field(default="pt-BR", max_length=20)
    privacy_policy_accepted: bool = Field(..., description="Must be True")
    tos_accepted: bool = Field(..., description="Must be True")


class OrcidConfirmLinkRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


class OrcidCompletionResponse(BaseModel):
    status: str
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    status: str
    slug: str
    locale: str
    roles: list[str]
    email_confirmed_at: str | None = None
    last_login_at: str | None = None
    created_at: str
    updated_at: str
    about: str | None = None
    link: str | None = None
    avatar_url: str | None = None
    approved_suggestions_count: int = 0


class PublicUserResponse(BaseModel):
    id: str
    full_name: str
    slug: str
    locale: str
    about: str | None = None
    link: str | None = None
    avatar_url: str | None = None
    approved_suggestions_count: int = 0


class PublicUserListResponse(BaseModel):
    data: list[PublicUserResponse]
    total: int
    limit: int
    offset: int


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    about: str | None = None
    link: str | None = None
    status: str | None = None
    role_key: str | None = None
    locale: str | None = None


class ChallengeResponse(BaseModel):
    challenge_id: str
    question: str


class DeleteAccountConfirmRequest(BaseModel):
    token: str


class ExportDataResponse(BaseModel):
    user: dict
    suggestions: list[dict]
    external_identities: list[dict] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str


# ── Suggestions ─────────────────────────────────────────────────────────────


class DocumentSuggestionResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    status: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    user_comment: str
    admin_comment: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    document_id: str | None = None
    ingested: bool = False
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str
    updated_at: str


class AdminBulkSuggestionFailureResponse(BaseModel):
    suggestion_id: str
    error: str


class AdminBulkApproveSuggestionsResponse(BaseModel):
    total_pending: int
    approved_count: int
    failed_count: int
    failures: list[AdminBulkSuggestionFailureResponse]


class DocumentSuggestionUpdateBody(BaseModel):
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    user_comment: str | None = None


class AdminDocumentSuggestionUpdateBody(BaseModel):
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    user_comment: str | None = None
    admin_comment: str | None = None


class AdminDocumentSuggestionDecisionBody(BaseModel):
    admin_comment: str | None = None
