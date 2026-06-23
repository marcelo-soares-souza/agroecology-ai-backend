CREATE TABLE IF NOT EXISTS document_academic_metadata_attempts (
    document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    last_error TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('enriched', 'no_match', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_attempts_status
    ON document_academic_metadata_attempts (status, attempted_at DESC);
