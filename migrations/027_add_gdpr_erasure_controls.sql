ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_version VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_version VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS erased_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS erasure_status VARCHAR(30) NOT NULL DEFAULT 'none';

UPDATE users
SET privacy_policy_version = '2026-06-25'
WHERE privacy_policy_accepted = TRUE
  AND privacy_policy_version IS NULL;

UPDATE users
SET tos_version = '2026-06-25'
WHERE tos_accepted = TRUE
  AND tos_version IS NULL;

ALTER TABLE document_suggestions
    ADD COLUMN IF NOT EXISTS personal_data_erased_at TIMESTAMPTZ;

ALTER TABLE document_suggestions
    ADD COLUMN IF NOT EXISTS attachment_erased_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS data_erasure_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    request_source VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error TEXT,
    CHECK (status IN ('pending', 'completed', 'failed')),
    CHECK (request_source IN ('account_delete', 'admin_delete', 'manual_request'))
);

CREATE INDEX IF NOT EXISTS idx_data_erasure_requests_user_requested
    ON data_erasure_requests (user_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_suggestions_personal_data_erased
    ON document_suggestions (personal_data_erased_at)
    WHERE personal_data_erased_at IS NOT NULL;
