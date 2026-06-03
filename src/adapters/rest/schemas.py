from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    task_id: str
    status: str


class AnswerResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None


class IngestionRunSchema(BaseModel):
    id: str
    status: str
    chunks_indexed: int
    error: str | None = None
    started_at: str
    finished_at: str | None = None


class StatusResponse(BaseModel):
    index_ready: bool
    ingest_status: str
    chunks_indexed: int
    active_tasks: int
    cache_enabled: bool
    cache_hits: int
    pending_docs: int = 0
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


class DocumentUpdateBody(BaseModel):
    title: str | None = None
    authors: str | None = None
    url: str | None = None
