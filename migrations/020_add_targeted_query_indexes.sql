CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- email_confirmations: token validation with purpose filter on unconfirmed rows.
CREATE INDEX IF NOT EXISTS idx_email_confirmations_token_purpose_pending
    ON email_confirmations (token_hash, purpose)
    WHERE confirmed_at IS NULL;

-- ingestion_runs: active run checks and latest active run lookup.
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_active_started
    ON ingestion_runs (started_at DESC)
    WHERE phase IN ('queued', 'processing');

-- document_suggestions: user-facing and admin listings filtered by user/status.
CREATE INDEX IF NOT EXISTS idx_document_suggestions_user_status_created
    ON document_suggestions (user_id, status, created_at DESC);

-- document_suggestions: fetch latest approved suggestion for a document.
CREATE INDEX IF NOT EXISTS idx_document_suggestions_document_approved_updated
    ON document_suggestions (document_id, updated_at DESC)
    WHERE status = 'approved' AND document_id IS NOT NULL;

-- document_suggestions: admin text search over title/authors/comment.
CREATE INDEX IF NOT EXISTS idx_document_suggestions_search_trgm
    ON document_suggestions
    USING GIN (
        (
            COALESCE(title, '') || E'\n' || COALESCE(authors, '') || E'\n'
            || COALESCE(user_comment, '')
        ) gin_trgm_ops
    );

-- job_queue: status breakdown per job type.
CREATE INDEX IF NOT EXISTS idx_job_queue_job_type_status
    ON job_queue (job_type, status);
