ALTER TABLE users
    ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS primary_auth_provider VARCHAR(50);

UPDATE users
SET primary_auth_provider = 'local'
WHERE primary_auth_provider IS NULL;

ALTER TABLE users
    ALTER COLUMN primary_auth_provider SET DEFAULT 'local';

ALTER TABLE user_external_identities
    ALTER COLUMN external_email DROP NOT NULL;

CREATE TABLE IF NOT EXISTS oauth_login_states (
    id TEXT PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    state_hash TEXT NOT NULL UNIQUE,
    nonce_hash TEXT,
    return_to TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oauth_login_states_provider_expires
    ON oauth_login_states (provider, expires_at);

CREATE TABLE IF NOT EXISTS external_login_completions (
    id TEXT PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    external_user_id VARCHAR(100) NOT NULL,
    external_slug VARCHAR(120),
    display_name VARCHAR(200),
    email VARCHAR(320),
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_external_login_completions_provider_user
    ON external_login_completions (provider, external_user_id);
