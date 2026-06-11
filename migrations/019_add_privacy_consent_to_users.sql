ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_accepted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_accepted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_accepted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_accepted_at TIMESTAMPTZ;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check;

ALTER TABLE users ADD CONSTRAINT users_status_check CHECK (status IN ('pending', 'active', 'suspended', 'deleted'));
