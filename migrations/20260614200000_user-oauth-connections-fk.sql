-- The user_id column on user_oauth_connections actually stores the API key principal's
-- org_id (developer_api_keys.org_id), which references organizations(id), not auth.users(id).
-- For seeded dev keys there's no corresponding auth.users row, so the original FK rejected inserts.

ALTER TABLE user_oauth_connections
  DROP CONSTRAINT IF EXISTS user_oauth_connections_user_id_fkey;

ALTER TABLE user_oauth_connections
  ADD CONSTRAINT user_oauth_connections_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES organizations(id) ON DELETE CASCADE;
