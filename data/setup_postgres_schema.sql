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
  follower_count integer,
  subscriber_count integer,
  avg_views integer,
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

-- Grant permissions to Roles
GRANT USAGE ON SCHEMA public TO anon, authenticated, project_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO anon, authenticated, project_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, project_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO anon, authenticated, project_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO anon, authenticated, project_admin;
