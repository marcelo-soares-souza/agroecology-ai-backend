CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    password_hash_version VARCHAR(50),
    full_name VARCHAR(200) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    email_confirmed_at TIMESTAMPTZ,
    slug VARCHAR(100) NOT NULL UNIQUE,
    last_login_at TIMESTAMPTZ,
    locale VARCHAR(10) NOT NULL DEFAULT 'pt-BR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('pending', 'active', 'suspended'))
);
