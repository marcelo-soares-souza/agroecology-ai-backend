CREATE TABLE IF NOT EXISTS document_academic_metadata (
    document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_id TEXT,
    doi TEXT,
    publication_year INTEGER,
    venue TEXT,
    publisher TEXT,
    citation_count INTEGER,
    reference_count INTEGER,
    abstract TEXT,
    source_url TEXT,
    open_access_url TEXT,
    topics JSONB,
    keywords JSONB,
    license JSONB,
    funder JSONB,
    match_confidence DOUBLE PRECISION,
    title_score DOUBLE PRECISION,
    author_score DOUBLE PRECISION,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_doi
    ON document_academic_metadata (doi)
    WHERE doi IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_citation_count
    ON document_academic_metadata (citation_count DESC)
    WHERE citation_count IS NOT NULL;

CREATE TABLE IF NOT EXISTS academic_metadata_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    documents_total INTEGER NOT NULL DEFAULT 0,
    documents_processed INTEGER NOT NULL DEFAULT 0,
    documents_enriched INTEGER NOT NULL DEFAULT 0,
    documents_skipped INTEGER NOT NULL DEFAULT 0,
    documents_failed INTEGER NOT NULL DEFAULT 0,
    delay_seconds INTEGER NOT NULL DEFAULT 60,
    current_document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    error TEXT,
    job_id TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('queued', 'processing', 'done', 'error')),
    CHECK (delay_seconds >= 60)
);

CREATE INDEX IF NOT EXISTS idx_academic_metadata_runs_status
    ON academic_metadata_runs (status, created_at DESC);

