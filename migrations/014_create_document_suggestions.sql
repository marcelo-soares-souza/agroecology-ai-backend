CREATE TABLE IF NOT EXISTS document_suggestions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    title TEXT,
    authors TEXT,
    url TEXT,
    user_comment TEXT NOT NULL,
    admin_comment TEXT,
    original_filename TEXT,
    file_type TEXT,
    file_size INTEGER,
    storage_directory TEXT,
    sha256 TEXT,
    document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_suggestions_status_check
        CHECK (status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT document_suggestions_pdf_type_check
        CHECK (file_type IS NULL OR file_type = 'pdf'),
    CONSTRAINT document_suggestions_has_source_check
        CHECK (url IS NOT NULL OR original_filename IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_document_suggestions_user_created
    ON document_suggestions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_suggestions_status_created
    ON document_suggestions (status, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_suggestions_sha256
    ON document_suggestions (sha256)
    WHERE sha256 IS NOT NULL;
