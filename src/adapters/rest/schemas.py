from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)
    history: list[dict] = Field(default_factory=list)


class AskResponse(BaseModel):
    task_id: str
    status: str


class AnswerResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str


class IngestionRunSchema(BaseModel):
    id: str
    status: str
    chunks_indexed: int
    error: str | None = None
    started_at: str
    finished_at: str | None = None


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
    status: str


class IngestStatusResponse(BaseModel):
    status: str
    chunks_indexed: int | None = None
    error: str | None = None
    run_id: str | None = None


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
    created_at: str
    updated_at: str


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


class LoginRequest(BaseModel):
    email: str
    password: str


class ConfirmEmailRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    status: str | None = None
    role_key: str | None = None
    locale: str | None = None


class ChallengeResponse(BaseModel):
    challenge_id: str
    question: str


class MessageResponse(BaseModel):
    message: str
