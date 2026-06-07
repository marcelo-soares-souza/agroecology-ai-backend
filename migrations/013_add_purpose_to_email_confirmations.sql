ALTER TABLE email_confirmations
ADD COLUMN IF NOT EXISTS purpose VARCHAR(32) NOT NULL DEFAULT 'email_confirmation';
CREATE INDEX IF NOT EXISTS idx_email_confirmations_purpose ON email_confirmations(purpose);
