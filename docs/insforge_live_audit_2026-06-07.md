# InsForge Live Backend Audit

Date: 2026-06-07

Project: `creatorScout` (`4c454309-a451-4184-a812-1e807739cdac`)
API base: `https://ffqsewe5.ap-southeast.insforge.app`
CLI user: authenticated through the InsForge CLI. Project API keys and user API keys were not copied into this note.

## Commands Run

- `npx @insforge/cli current --json`
- `npx @insforge/cli metadata --json`
- `npx @insforge/cli db tables --json`
- `npx @insforge/cli db policies --json`
- `npx @insforge/cli storage buckets --json`
- `npx @insforge/cli db migrations list --json`
- Column, grant, RLS, and index inspection queries against `information_schema`, `pg_class`, and `pg_indexes`.
- `npx @insforge/cli branch list --json`

## Current State

Expected tables from `data/setup_postgres_schema.sql` exist:

- `organizations`
- `creator_profiles`
- `creator_accounts`
- `creator_contacts`
- `creator_index_sources`
- `brands`
- `brand_pages`
- `campaigns`
- `campaign_discovery_jobs`
- `campaign_creators`
- `outreach_messages`
- `developer_api_keys`
- `api_credit_ledger`
- `api_usage_events`
- `discovery_jobs`
- `provider_requests`

Live record counts from metadata:

- `creator_profiles`: 141
- `creator_accounts`: 148
- `creator_contacts`: 58
- `campaigns`: 32
- `campaign_discovery_jobs`: 154
- `campaign_creators`: 76
- `discovery_jobs`: 154
- `provider_requests`: 100
- `developer_api_keys`: 1

Operational gaps confirmed:

- `campaign_exports` does not exist.
- `discovery_jobs` does not have `attempt_count`, `max_attempts`, `next_run_at`, `locked_at`, or `locked_by`.
- Storage has no buckets. The planned private bucket is `campaign-exports`.
- `db policies` returned no RLS policies.
- RLS is disabled for all public app tables.
- `anon` and `authenticated` currently have broad table privileges on public app tables, including `SELECT`, `INSERT`, `UPDATE`, `DELETE`, and `TRUNCATE`.
- Remote migrations list is empty.
- Backend branch support is available; branch list returned no active branches.

## Safety Notes

- The linked project contains live data. Test runs must not clear the parent project.
- Apply backend hardening on an InsForge branch first, then merge only after API smoke checks pass.
- Server code should use `INSFORGE_API_BASE_URL` and `INSFORGE_API_KEY`. `NEXT_PUBLIC_INSFORGE_URL` and `NEXT_PUBLIC_INSFORGE_ANON_KEY` are browser-auth/client fallback variables only and must not be used as server admin credentials.
