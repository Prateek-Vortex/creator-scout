-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create organizations table if not exists
CREATE TABLE IF NOT EXISTS organizations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name text NOT null,
  slug text,
  plan text NOT null DEFAULT 'free',
  created_at timestamp with time zone NOT null DEFAULT now(),
  updated_at timestamp with time zone NOT null DEFAULT now()
);

-- Insert our demo organization
INSERT INTO organizations (id, name, slug, plan)
VALUES ('e1e3e5a6-6d57-4600-9eb0-928e00f3bbf7', 'Creator Scout Demo Team', 'creator-scout-demo', 'free')
ON CONFLICT (id) DO NOTHING;

-- Creator Scout Tables
CREATE TABLE IF NOT EXISTS creator_profiles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  display_name text NOT null,
  primary_niche text,
  location text,
  languages text[] DEFAULT '{}'::text[],
  summary text,
  topics text[] DEFAULT '{}'::text[],
  raw_json jsonb NOT null DEFAULT '{}'::jsonb,
  embedding vector(1536),
  created_at timestamp with time zone NOT null DEFAULT now(),
  updated_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS creator_accounts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  creator_id uuid REFERENCES creator_profiles(id) ON DELETE CASCADE,
  platform text NOT null,
  handle text NOT null,
  profile_url text NOT null UNIQUE,
  follower_count bigint,
  subscriber_count bigint,
  avg_views bigint,
  engagement_rate numeric,
  bio text,
  raw_json jsonb NOT null DEFAULT '{}'::jsonb,
  last_verified_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS creator_contacts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  creator_id uuid REFERENCES creator_profiles(id) ON DELETE CASCADE,
  contact_type text NOT null,
  value text NOT null,
  source_url text NOT null,
  source_type text NOT null DEFAULT 'public_business_contact',
  permission_basis text NOT null DEFAULT 'public_business_contact',
  confidence text NOT null DEFAULT 'medium',
  do_not_contact boolean NOT null DEFAULT false,
  last_verified_at timestamp with time zone NOT null DEFAULT now(),
  created_at timestamp with time zone NOT null DEFAULT now(),
  UNIQUE(creator_id, contact_type, value)
);

CREATE TABLE IF NOT EXISTS creator_index_sources (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  creator_id uuid REFERENCES creator_profiles(id) ON DELETE CASCADE,
  account_id uuid,
  source_type text NOT null,
  source_url text NOT null,
  source_provider text,
  source_hash text,
  crawl_allowed boolean,
  fields_found jsonb NOT null DEFAULT '{}'::jsonb,
  confidence numeric,
  fetched_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS brands (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  website_url text NOT null,
  name text,
  brief_json jsonb NOT null DEFAULT '{}'::jsonb,
  confidence numeric,
  category text,
  target_audience text,
  price_positioning text,
  tone text[] DEFAULT '{}'::text[],
  value_props text[] DEFAULT '{}'::text[],
  created_at timestamp with time zone NOT null DEFAULT now(),
  updated_at timestamp with time zone NOT null DEFAULT now()
);

-- Create index for brand_pages relationship
CREATE TABLE IF NOT EXISTS brand_pages (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  brand_id uuid REFERENCES brands(id) ON DELETE CASCADE,
  source_url text NOT null,
  title text,
  page_type text,
  markdown text,
  extracted_json jsonb NOT null DEFAULT '{}'::jsonb,
  fetched_at timestamp with time zone,
  fetch_status text,
  robots_allowed boolean DEFAULT true,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  brand_id uuid REFERENCES brands(id) ON DELETE CASCADE,
  brand_url text NOT null,
  goal text NOT null,
  geography text NOT null,
  platforms text[] DEFAULT '{}'::text[],
  status text NOT null DEFAULT 'draft',
  brief_json jsonb NOT null DEFAULT '{}'::jsonb,
  search_queries text[] DEFAULT '{}'::text[],
  created_at timestamp with time zone NOT null DEFAULT now(),
  updated_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaign_discovery_jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id uuid NOT null REFERENCES campaigns(id) ON DELETE CASCADE,
  job_id uuid NOT null,
  query text NOT null,
  provider text NOT null,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaign_creators (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  creator_id uuid REFERENCES creator_profiles(id) ON DELETE CASCADE,
  status text NOT null DEFAULT 'shortlisted',
  bucket text,
  fit_score integer,
  score_breakdown jsonb NOT null DEFAULT '{}'::jsonb,
  evidence jsonb NOT null DEFAULT '[]'::jsonb,
  risks jsonb NOT null DEFAULT '[]'::jsonb,
  unknowns jsonb NOT null DEFAULT '[]'::jsonb,
  recommended_pitch text,
  outreach_draft jsonb,
  notes text,
  next_followup_at timestamp with time zone,
  created_at timestamp with time zone NOT null DEFAULT now(),
  updated_at timestamp with time zone NOT null DEFAULT now(),
  UNIQUE(campaign_id, creator_id)
);

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

CREATE TABLE IF NOT EXISTS outreach_messages (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_creator_id uuid REFERENCES campaign_creators(id) ON DELETE CASCADE,
  channel text NOT null DEFAULT 'email',
  subject text,
  body text NOT null,
  tone text DEFAULT 'warm',
  status text NOT null DEFAULT 'draft',
  sequence_order integer DEFAULT 1,
  sent_at timestamp with time zone,
  opened_at timestamp with time zone,
  replied_at timestamp with time zone,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS developer_api_keys (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT null REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT null,
  key_hash text NOT null UNIQUE,
  scopes jsonb NOT null DEFAULT '[]'::jsonb,
  rate_limit_per_minute integer NOT null DEFAULT 60,
  monthly_credit_limit numeric NOT null,
  revoked_at timestamp with time zone,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_credit_ledger (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT null REFERENCES organizations(id) ON DELETE CASCADE,
  api_key_id uuid REFERENCES developer_api_keys(id) ON DELETE SET NULL,
  event_type text NOT null,
  endpoint text,
  credits numeric NOT null,
  balance_after numeric,
  request_id text,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_usage_events (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid not null REFERENCES organizations(id) ON DELETE CASCADE,
  api_key_id uuid REFERENCES developer_api_keys(id) ON DELETE SET NULL,
  request_id text NOT null,
  endpoint text not null,
  status_code integer,
  latency_ms integer,
  cache_status text,
  credits_charged numeric,
  result_count integer,
  created_at timestamp with time zone NOT null DEFAULT now()
);

CREATE TABLE IF NOT EXISTS discovery_jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  requested_by_api_key_id uuid REFERENCES developer_api_keys(id) ON DELETE SET NULL,
  job_type text NOT null,
  provider text,
  status text NOT null DEFAULT 'queued',
  input jsonb NOT null DEFAULT '{}'::jsonb,
  output jsonb NOT null DEFAULT '{}'::jsonb,
  error text,
  attempt_count integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  next_run_at timestamp with time zone,
  locked_at timestamp with time zone,
  locked_by text,
  created_at timestamp with time zone NOT null DEFAULT now(),
  started_at timestamp with time zone,
  finished_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS provider_requests (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  campaign_id uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  job_id uuid,
  provider text NOT null,
  endpoint text,
  request_hash text,
  response_status integer,
  response_summary jsonb NOT null DEFAULT '{}'::jsonb,
  cost_units numeric,
  rate_limit_remaining integer,
  cached boolean NOT null DEFAULT false,
  created_at timestamp with time zone NOT null DEFAULT now()
);

-- RPC Function
CREATE OR REPLACE FUNCTION match_creators(
  query_embedding vector(1536),
  match_threshold float,
  match_limit int
) RETURNS TABLE (
  id uuid,
  display_name text,
  primary_niche text,
  similarity float
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    creator_profiles.id,
    creator_profiles.display_name,
    creator_profiles.primary_niche,
    (1 - (creator_profiles.embedding <=> query_embedding))::float AS similarity
  FROM creator_profiles
  WHERE creator_profiles.embedding IS NOT NULL 
    AND 1 - (creator_profiles.embedding <=> query_embedding) > match_threshold
  ORDER BY creator_profiles.embedding <=> query_embedding
  LIMIT match_limit;
END;
$$;

CREATE INDEX IF NOT EXISTS discovery_jobs_ready_idx
  ON discovery_jobs (status, next_run_at, created_at);

CREATE INDEX IF NOT EXISTS discovery_jobs_locked_idx
  ON discovery_jobs (locked_at)
  WHERE locked_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS campaign_exports_campaign_id_created_at_idx
  ON campaign_exports (campaign_id, created_at DESC);

CREATE INDEX IF NOT EXISTS campaign_exports_org_id_created_at_idx
  ON campaign_exports (org_id, created_at DESC);

-- Server API access is project-admin only. Browser auth uses InsForge Auth and
-- the public SDK client, but direct browser table access is intentionally closed.
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
