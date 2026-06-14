-- Per-user OAuth provider connections (Gmail send today; extensible to other providers).
-- Tokens are encrypted at the application layer with OAUTH_TOKEN_ENCRYPTION_KEY (Fernet);
-- this table stores ciphertext only, so a raw row leak does not expose live credentials.

CREATE TABLE IF NOT EXISTS user_oauth_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  provider text NOT NULL,
  email text,
  access_token text,
  refresh_token text NOT NULL,
  expires_at timestamp with time zone,
  scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS user_oauth_connections_user_idx
  ON user_oauth_connections (user_id);

ALTER TABLE user_oauth_connections ENABLE ROW LEVEL SECURITY;

-- Users can read and delete (disconnect) their own row from the browser.
-- All writes (insert/refresh) happen server-side via the InsForge API key, which
-- bypasses RLS — keeping refresh tokens off the wire to the browser.
DROP POLICY IF EXISTS authenticated_select_own_oauth ON user_oauth_connections;
CREATE POLICY authenticated_select_own_oauth ON user_oauth_connections
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS authenticated_delete_own_oauth ON user_oauth_connections;
CREATE POLICY authenticated_delete_own_oauth ON user_oauth_connections
  FOR DELETE TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS project_admin_all_oauth ON user_oauth_connections;
CREATE POLICY project_admin_all_oauth ON user_oauth_connections
  FOR ALL TO project_admin USING (true) WITH CHECK (true);
