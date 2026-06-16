UPDATE user_external_identities AS identity
SET deleted_at = COALESCE(identity.deleted_at, NOW()),
    updated_at = NOW()
FROM users
WHERE identity.user_id = users.id
  AND users.status = 'deleted'
  AND identity.deleted_at IS NULL;
