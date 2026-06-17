CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- documents: paginated search uses ILIKE across these fields.
CREATE INDEX IF NOT EXISTS idx_documents_filename_trgm
    ON documents USING GIN (filename gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_title_trgm
    ON documents USING GIN (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_authors_trgm
    ON documents USING GIN (authors gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_url_trgm
    ON documents USING GIN (url gin_trgm_ops);

-- documents: paginated listing without search orders by title, filename, then creation date.
CREATE INDEX IF NOT EXISTS idx_documents_title_filename_created
    ON documents (title ASC NULLS LAST, filename ASC, created_at DESC);

-- users: public active-user listing searches by name/slug and sorts by recent updates.
CREATE INDEX IF NOT EXISTS idx_users_active_full_name_trgm
    ON users USING GIN (full_name gin_trgm_ops)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_users_active_slug_trgm
    ON users USING GIN (slug gin_trgm_ops)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_users_active_updated_full_name
    ON users (updated_at DESC, full_name ASC)
    WHERE status = 'active';

-- user_roles: admin-role locking starts from role_key and joins through role_id.
CREATE INDEX IF NOT EXISTS idx_user_roles_role_user
    ON user_roles (role_id, user_id);
