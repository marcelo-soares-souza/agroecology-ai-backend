CREATE TABLE IF NOT EXISTS user_external_identities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    external_user_id VARCHAR(100) NOT NULL,
    external_email VARCHAR(320) NOT NULL,
    external_slug VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (provider, external_user_id),
    UNIQUE (provider, external_email)
);

CREATE INDEX IF NOT EXISTS idx_user_external_identities_user_id
    ON user_external_identities (user_id)
    WHERE deleted_at IS NULL;
