-- email_confirmations: token lookup (Q40)
CREATE INDEX IF NOT EXISTS idx_email_confirmations_token_hash
    ON email_confirmations (token_hash);

-- refresh_tokens: token lookup / single revoke (Q43, Q45)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
    ON refresh_tokens (token_hash);

-- refresh_tokens: revoke all tokens for a user (Q44)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_revoked
    ON refresh_tokens (user_id, revoked_at);

-- document_suggestions: FK join to documents (Q51-Q54)
CREATE INDEX IF NOT EXISTS idx_document_suggestions_document_id
    ON document_suggestions (document_id);

-- documents: main listing (Q15)
CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON documents (created_at DESC);

-- documents: duplicate filename check (Q18)
CREATE INDEX IF NOT EXISTS idx_documents_filename
    ON documents (filename);

-- ingestion_runs: history listing (Q23)
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at
    ON ingestion_runs (started_at DESC);

-- job_queue: replace partial index to include created_at for ORDER BY (Q61)
DROP INDEX IF EXISTS idx_job_queue_pending;
CREATE INDEX IF NOT EXISTS idx_job_queue_pending_fetch
    ON job_queue (status, scheduled_at, created_at)
    WHERE status = 'pending';

-- job_queue: stats by job type (Q62)
CREATE INDEX IF NOT EXISTS idx_job_queue_job_type
    ON job_queue (job_type);

-- users: admin listing (Q33)
CREATE INDEX IF NOT EXISTS idx_users_created_at
    ON users (created_at DESC);

-- users: active users listing — filter + order (Q34)
CREATE INDEX IF NOT EXISTS idx_users_status_last_login
    ON users (status, last_login_at DESC NULLS LAST);
