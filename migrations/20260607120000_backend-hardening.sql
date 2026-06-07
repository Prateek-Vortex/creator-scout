-- Creator Scout backend hardening.
-- Apply on an InsForge branch first, then merge after API smoke checks pass.

ALTER TABLE discovery_jobs
  ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS next_run_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS locked_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS locked_by text;

UPDATE discovery_jobs
SET max_attempts = 3
WHERE max_attempts IS NULL OR max_attempts < 1;

CREATE INDEX IF NOT EXISTS discovery_jobs_ready_idx
  ON discovery_jobs (status, next_run_at, created_at);

CREATE INDEX IF NOT EXISTS discovery_jobs_locked_idx
  ON discovery_jobs (locked_at)
  WHERE locked_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS campaign_exports (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  campaign_id uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  storage_key text NOT NULL,
  file_url text NOT NULL,
  row_count integer NOT NULL DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS campaign_exports_campaign_id_created_at_idx
  ON campaign_exports (campaign_id, created_at DESC);

CREATE INDEX IF NOT EXISTS campaign_exports_org_id_created_at_idx
  ON campaign_exports (org_id, created_at DESC);

GRANT USAGE ON SCHEMA public TO project_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO project_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO project_admin;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO project_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO project_admin;

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_discovery_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_creators ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE developer_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_credit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_index_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS project_admin_all_organizations ON organizations;
CREATE POLICY project_admin_all_organizations ON organizations FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_brands ON brands;
CREATE POLICY project_admin_all_brands ON brands FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_brand_pages ON brand_pages;
CREATE POLICY project_admin_all_brand_pages ON brand_pages FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_campaigns ON campaigns;
CREATE POLICY project_admin_all_campaigns ON campaigns FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_campaign_discovery_jobs ON campaign_discovery_jobs;
CREATE POLICY project_admin_all_campaign_discovery_jobs ON campaign_discovery_jobs FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_campaign_creators ON campaign_creators;
CREATE POLICY project_admin_all_campaign_creators ON campaign_creators FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_campaign_exports ON campaign_exports;
CREATE POLICY project_admin_all_campaign_exports ON campaign_exports FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_outreach_messages ON outreach_messages;
CREATE POLICY project_admin_all_outreach_messages ON outreach_messages FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_developer_api_keys ON developer_api_keys;
CREATE POLICY project_admin_all_developer_api_keys ON developer_api_keys FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_api_credit_ledger ON api_credit_ledger;
CREATE POLICY project_admin_all_api_credit_ledger ON api_credit_ledger FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_api_usage_events ON api_usage_events;
CREATE POLICY project_admin_all_api_usage_events ON api_usage_events FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_discovery_jobs ON discovery_jobs;
CREATE POLICY project_admin_all_discovery_jobs ON discovery_jobs FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_provider_requests ON provider_requests;
CREATE POLICY project_admin_all_provider_requests ON provider_requests FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_creator_profiles ON creator_profiles;
CREATE POLICY project_admin_all_creator_profiles ON creator_profiles FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_creator_accounts ON creator_accounts;
CREATE POLICY project_admin_all_creator_accounts ON creator_accounts FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_creator_contacts ON creator_contacts;
CREATE POLICY project_admin_all_creator_contacts ON creator_contacts FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_creator_index_sources ON creator_index_sources;
CREATE POLICY project_admin_all_creator_index_sources ON creator_index_sources FOR ALL TO project_admin USING (true) WITH CHECK (true);
