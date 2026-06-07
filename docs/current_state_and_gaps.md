# Creator Scout Current State And Gaps

Date: 2026-06-07

This document is the canonical current-state reference for the repo. When older PRD/spec files disagree, prefer this file plus the code in `apps/api`, `apps/web`, and `creator_scout`.

## Source Of Truth

- Current UI direction: `DESIGN_SYSTEM.md`, `.gemini/ui-skills.md`, `apps/web/src/app/globals.css`, and `apps/web/src/app/page.tsx`.
- Current API/runtime code: `apps/api/server.py` and `creator_scout/`.
- Current data model: `data/setup_postgres_schema.sql` plus migration files under `migrations/`.
- Live backend audit: `docs/insforge_live_audit_2026-06-07.md`.
- Branch backend verification: `docs/insforge_branch_verification_2026-06-07.md`.

`implementation_plan.md` is now a short active-direction note. The older dark/neon UI redesign plan is obsolete; keep the warm cream Sticker Notebook system unless the user explicitly asks for a redesign.

## Current Architecture

### Web App

`apps/web` is a Next.js 16 App Router frontend using React 19, Framer Motion, Tailwind CSS 4, and `@insforge/sdk`.

- `apps/web/src/lib/insforge.ts` creates the browser InsForge auth client from `NEXT_PUBLIC_INSFORGE_URL` and `NEXT_PUBLIC_INSFORGE_ANON_KEY`.
- `apps/web/src/lib/api.ts` calls the Python API. Browser requests go through Next rewrites under `/api/*`; server-side requests use `NEXT_PUBLIC_CREATOR_SCOUT_API_URL` or `http://127.0.0.1:8765`.
- `apps/web/next.config.ts` rewrites `/api/v1/*` to the Python API's `/v1/*` routes and `/api/health` to `/health`.
- `apps/web/src/app/page.tsx` contains the current landing/workspace experience, campaign launch flow, job status display, creator shortlist flow, outreach composer, CRM-lite board, and server-side CSV export action.

The UI theme is the warm cream Sticker Notebook system: paper surfaces, sticker cards, badge stickers, Caveat handwriting accents, and Framer Motion entrances. Do not replace it with the obsolete dark/neon plan.

### Python API

`apps/api/server.py` is a lightweight `http.server` service bound by default to `127.0.0.1:8765`.

Implemented routes include:

- `POST /v1/discovery/search`
- `POST /v1/brand-scans`
- `GET /v1/brands/{brand_id}`
- `POST /v1/campaigns`
- `GET /v1/campaigns/{campaign_id}`
- `POST /v1/campaigns/{campaign_id}/shortlist`
- `GET /v1/campaigns/{campaign_id}/creators`
- `PATCH /v1/campaigns/{campaign_id}/creators/{creator_id}`
- `POST /v1/campaigns/{campaign_id}/export`
- `GET /v1/creators/{creator_id}`
- `POST /v1/discovery/refresh`
- `POST /v1/discovery/ingest-query`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/usage`
- `GET /health`

The active backend store is InsForge Postgres/REST/AI/Storage, not local SQLite. Server-side Python processes should use `INSFORGE_API_BASE_URL` and `INSFORGE_API_KEY`. `NEXT_PUBLIC_INSFORGE_URL` and `NEXT_PUBLIC_INSFORGE_ANON_KEY` are only for the browser auth client; the store keeps a local fallback warning for old dev setups.

### InsForge Store And AI Gateway

`creator_scout/discovery/store.py` is the persistence layer. It reads server-only credentials first:

- `INSFORGE_API_BASE_URL`
- `INSFORGE_API_KEY`

It writes and reads records through InsForge database endpoints such as `/api/database/records/creator_profiles`, `/api/database/records/campaigns`, `/api/database/records/discovery_jobs`, `/api/database/records/campaign_creators`, and `/api/database/records/campaign_exports`.

It also uses InsForge AI endpoints:

- `/api/ai/embeddings` for creator embeddings.
- `/api/ai/chat/completion` for brand brief extraction, creator scoring, and outreach draft generation.

CSV exports are uploaded to the private InsForge Storage bucket `campaign-exports` and recorded in `campaign_exports`.

## Creator Discovery Flow

1. A user enters a brand URL in the web app.
2. `apps/web/src/app/page.tsx` calls `api.createCampaign(...)` with `provider: "youtube"` by default.
3. `DiscoveryService.create_campaign()` delegates to `CampaignService.create_campaign()`.
4. `CampaignService` runs `BrandScanService.scan()`.
5. `BrandScanService` uses the custom `BrandCrawler`, not Firecrawl/TinyFish, to fetch the brand site.
6. `build_brand_brief()` tries the InsForge AI gateway for a structured brand brief and falls back to heuristic extraction if the AI call fails.
7. The brand scan is saved to InsForge `brands` and `brand_pages`.
8. Campaign search queries are saved to InsForge `campaigns`.
9. For each query, the campaign queues a `creator_discovery_query` job using one provider, usually `youtube`.
10. The polling worker must run separately with `python -m creator_scout.discovery.worker --loop --interval 30`.
11. The worker calls the selected adapter, normalizes raw records, and saves creator profiles, accounts, contacts, and sources to InsForge.
12. Campaign API responses include `job_summary` so the UI can show queued/running/passed/failed counts and poll while jobs are pending.
13. The UI blocks "Build shortlist" while jobs are queued/running. Shortlisting ranks currently cached/indexed creators after pending jobs finish or fail.

## Provider Usage

### YouTube

`creator_scout/discovery/adapters/youtube.py` uses the official YouTube Data API.

- `discover()` calls `search.list` with `type=channel`.
- It hydrates channels with `channels.list`.
- It stores channel data as YouTube creator accounts and `youtube_data_api` source evidence.
- It requires `YOUTUBE_API_KEY`.

### TinyFish

`creator_scout/discovery/adapters/tinyfish.py` uses TinyFish Search and Fetch only.

- `discover()` calls TinyFish search and creates shallow records from public search results.
- `fetch_profile()` calls TinyFish fetch for explicit allowed URLs and extracts public emails from returned content.
- The code does not use TinyFish Browser or Agent APIs.
- It requires `TINYFISH_API_KEY`.

### Firecrawl

`creator_scout/discovery/adapters/firecrawl.py` only supports explicit creator-owned/profile URL scraping.

- `discover()` raises `AdapterError("FirecrawlAdapter requires explicit creator-owned URLs")`.
- `fetch_profile()` calls Firecrawl scrape for a specific allowed URL, extracts public emails, and finds public social links.
- Firecrawl is not used by the current brand crawler.
- It requires `FIRECRAWL_API_KEY`.

### Public Web

`creator_scout/discovery/adapters/public_web.py` is a robots-aware fetcher for explicit creator-owned pages such as sites and media kits.

- `discover()` raises because query discovery is not supported.
- `fetch_profile()` checks compliance rules, checks robots.txt, fetches the page, extracts visible public emails and public social links, and stores `creator_owned_site` source evidence.

### Restricted Platforms And Compliance

`creator_scout/discovery/compliance.py` blocks fetches for restricted social domains including Instagram, TikTok, LinkedIn, and Facebook, plus gated/login-like paths.

Instagram, TikTok, and LinkedIn appear as UI/platform fields and normalized account platforms, but there is no official ingestion adapter for them in this repo. The code does not implement unauthorized scraping of those platforms.

## Backend Hardening State

- Live InsForge schema audit was captured before migration in `docs/insforge_live_audit_2026-06-07.md`.
- Hardening migration lives at `migrations/20260607120000_backend-hardening.sql`.
- Count-column migration lives at `migrations/20260607121000_creator-account-count-bigints.sql`.
- The migration adds retry/lock fields to `discovery_jobs`, adds `campaign_exports`, revokes broad app-table grants from `anon` and `authenticated`, enables RLS on app tables, and grants project-admin policies for server API access.
- The migrations have been applied to the `mvp-hardening` InsForge branch and verified there. Merge to the parent project should happen only after branch smoke tests pass.
- The private `campaign-exports` storage bucket exists on the branch. Create or verify it on the parent project when merging the backend change.

## Current UI State

The intended UI is the Sticker Notebook design system:

- Warm cream page background (`#faf9f6`).
- Paper surfaces via `.notebook-page`, `.sticker-card`, `.glass-card`, and `.glass-panel`.
- Accent badges via `.badge-sticker` with coral, teal, lavender, and amber variants.
- Framer Motion entrance and interaction animations.
- Inter/Geist body typography, JetBrains Mono for code/data, and Caveat for short handwriting accents.

Current workflow additions preserve this style:

- Strategy tab shows job counts by status: queued, running, passed, failed.
- Build shortlist is disabled while queued/running jobs remain.
- Platform copy says Instagram/TikTok are cached/indexed filters until official adapters exist.
- CRM status, recommended pitch, and private notes are persisted through the API.
- CSV export is server-side and persists metadata in InsForge.

## Remaining Gaps

### Discovery

- Campaign creation uses one provider for all generated queries, defaulting to `youtube`.
- TinyFish query discovery creates shallow records from search results. TinyFish Fetch is only used for explicit URLs.
- Firecrawl and public web cannot discover creators from a query.
- Brand crawler fetch failures produce a synthesized fallback page and heuristic brief. This is useful for demos, but fallback confidence and provenance should be surfaced more explicitly to users.

### Architecture

- LangGraph and the multi-agent workflow are in the technical spec only; the implemented workflow is deterministic Python services plus a polling worker.
- The worker has Docker packaging but is not yet deployed as a managed InsForge compute service from this repo state.
- Run one managed worker instance initially. Multi-worker locking is intentionally deferred even though lock metadata now exists.
- There is no Redis-backed rate limiting, queue, or provider concurrency control.

### Product

- Outreach drafts exist, but there is no compliant sending workflow.
- There is no unsubscribe, suppression list, bounce handling, sender verification, Gmail OAuth sending, or AutoSend integration.
- Billing through Dodo/Stripe is not implemented.
- Lifecycle/product email automation through AutoSend is not implemented.
- Contact enrichment is basic public email extraction from allowed public text, not a full enrichment/verifier workflow.

### Data And Compliance

- Parent-project RLS/grant hardening should not be treated as complete until the branch migration is merged and parent smoke tests pass.
- Provider request logging exists in `provider_requests`, but TinyFish run IDs/browser metadata are not stored because Browser/Agent APIs are not used.
- Contact provenance is stored through contacts and sources, but there is no suppression/do-not-contact workflow beyond the `do_not_contact` contact field.
- Restricted social domains are blocked for public fetches; product copy should continue avoiding any implication of direct Instagram/TikTok/LinkedIn scraping.

## Verification Notes

Checked locally against:

- `tinyfish`, `firecrawl`, `youtube`, `provider`
- `BrandCrawler`
- `LangGraph`
- `Modash`
- `SQLite`
- `RLS`
- `run_id`, `browser`, `agent`

Validation for this change set should include Python compile checks, frontend lint/build, branch schema inspection, and branch API smoke tests before merging InsForge backend changes to the parent project.
