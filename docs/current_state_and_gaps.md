# Creator Scout Current State And Gaps

Date: 2026-06-07

This document captures the repo's current implementation state. It is intended to resolve drift between the older product/spec docs, the current InsForge-backed code, and the active Sticker Notebook UI direction.

## Source Of Truth

- Current UI direction: `DESIGN_SYSTEM.md`, `.gemini/ui-skills.md`, `apps/web/src/app/globals.css`, and `apps/web/src/app/page.tsx`.
- Current API/runtime code: `apps/api/server.py` and `creator_scout/`.
- Current data model: `data/setup_postgres_schema.sql` plus the InsForge REST calls in `creator_scout/discovery/store.py`.
- Stale/conflicting UI plan: `implementation_plan.md`. It proposes a dark neon/glassmorphism redesign, which conflicts with the warm cream Sticker Notebook system and should be treated as obsolete unless explicitly revived.

## Current Architecture

### Web App

`apps/web` is a Next.js 16 App Router frontend using React 19, Framer Motion, Tailwind CSS 4, and `@insforge/sdk`.

- `apps/web/src/lib/insforge.ts` creates the browser InsForge auth client from `NEXT_PUBLIC_INSFORGE_URL` and `NEXT_PUBLIC_INSFORGE_ANON_KEY`.
- `apps/web/src/lib/api.ts` is a custom fetch client for the local Python API. Browser requests go through Next rewrites under `/api/*`; server-side requests use `NEXT_PUBLIC_CREATOR_SCOUT_API_URL` or `http://127.0.0.1:8765`.
- `apps/web/next.config.ts` rewrites `/api/v1/*` to the Python API's `/v1/*` routes and `/api/health` to `/health`.
- `apps/web/src/app/page.tsx` contains the current landing/workspace experience, campaign launch flow, creator shortlist flow, outreach composer, CRM-lite board, and browser-side CSV export.

The UI theme is the warm cream Sticker Notebook system: paper surfaces, sticker cards, badge stickers, Caveat handwriting accents, and Framer Motion entrances. Do not replace it with the dark/neon plan in `implementation_plan.md`.

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
- `GET /v1/creators/{creator_id}`
- `POST /v1/discovery/refresh`
- `POST /v1/discovery/ingest-query`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/usage`
- `GET /health`

The server still defines `CREATOR_SCOUT_DB` and passes a path into `DiscoveryStore`, but `DiscoveryStore` currently ignores that path for persistence and requires InsForge env vars. The active backend store is InsForge Postgres/REST/AI, not local SQLite.

### InsForge Store And AI Gateway

`creator_scout/discovery/store.py` is the persistence layer. It reads:

- `NEXT_PUBLIC_INSFORGE_URL`
- `NEXT_PUBLIC_INSFORGE_ANON_KEY`

It writes and reads records through InsForge database endpoints such as `/api/database/records/creator_profiles`, `/api/database/records/campaigns`, `/api/database/records/discovery_jobs`, and `/api/database/records/provider_requests`.

It also uses InsForge AI endpoints:

- `/api/ai/embeddings` for creator embeddings.
- `/api/ai/chat/completion` for brand brief extraction, creator scoring, and outreach draft generation.

The schema in `data/setup_postgres_schema.sql` defines organizations, creators, accounts, contacts, sources, brands, brand pages, campaigns, campaign jobs, campaign creators, outreach messages, API keys, credit ledgers, usage events, discovery jobs, provider request logs, and a `match_creators` pgvector RPC.

### Python Modules

- `creator_scout/brand/`: brand crawling, brand page models, brand brief extraction, and brand scan service.
- `creator_scout/campaign/`: campaign creation, discovery job queueing, shortlist building, outreach draft generation, and campaign creator persistence.
- `creator_scout/discovery/`: auth, search, scoring, normalization, ingestion, provider adapters, job queue helpers, polling worker, and InsForge store.

## Creator Discovery Flow

1. A user enters a brand URL in the web app.
2. `apps/web/src/app/page.tsx` calls `api.createCampaign(...)` with `provider: "youtube"` by default.
3. `DiscoveryService.create_campaign()` delegates to `CampaignService.create_campaign()`.
4. `CampaignService` runs `BrandScanService.scan()`.
5. `BrandScanService` uses the custom `BrandCrawler`, not Firecrawl/TinyFish, to fetch the brand site.
6. `build_brand_brief()` tries the InsForge AI gateway for a structured brand brief and falls back to heuristic extraction if the AI call fails.
7. The brand scan is saved to InsForge `brands` and `brand_pages`.
8. Campaign search queries from the brief are saved to InsForge `campaigns`.
9. For each query, the campaign queues a `creator_discovery_query` job using one provider, usually `youtube`.
10. The polling worker (`python -m creator_scout.discovery.worker`) must run separately to process queued jobs.
11. The worker calls the selected adapter, normalizes raw records, and saves creator profiles, accounts, contacts, and sources to InsForge.
12. Shortlisting runs against the currently stored creator index. It ranks cached/indexed creators; it does not wait for queued jobs or automatically run the worker.

This means a newly created campaign can have queued provider jobs before there are fresh provider results in the shortlist. Fresh results only exist after the worker processes the jobs and ingestion succeeds.

## Provider Usage

### YouTube

`creator_scout/discovery/adapters/youtube.py` uses the official YouTube Data API.

- `discover()` calls `search.list` with `type=channel`.
- It hydrates channels with `channels.list`.
- It stores channel data as YouTube creator accounts and `youtube_data_api` source evidence.
- It requires `YOUTUBE_API_KEY`.

### TinyFish

`creator_scout/discovery/adapters/tinyfish.py` uses TinyFish Search and Fetch only.

- `discover()` calls `https://api.search.tinyfish.ai` and creates shallow records from public search results.
- `fetch_profile()` calls `https://api.fetch.tinyfish.ai` for explicit allowed URLs and extracts public emails from returned content.
- The code does not use TinyFish Browser or Agent APIs, and it does not store TinyFish run IDs, browser session IDs, goals, or browser metadata.
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

### Modash

There is no Modash adapter or runtime dependency. Existing references treat Modash as a competitor/benchmark, not a provider.

## Current UI State

The intended UI is the Sticker Notebook design system:

- Warm cream page background (`#faf9f6`).
- Paper surfaces via `.notebook-page`, `.sticker-card`, `.glass-card`, and `.glass-panel`.
- Accent badges via `.badge-sticker` with coral, teal, lavender, and amber variants.
- Framer Motion entrance and interaction animations.
- Inter/Geist body typography, JetBrains Mono for code/data, and Caveat for short handwriting accents.

`implementation_plan.md` conflicts with this because it proposes a Midnight Violet/Teal Glow dark theme with glassmorphism and neon accents. Treat it as stale for UI work.

No UI, theme, schema, provider, or behavior changes are made by this document.

## Priority Gaps

### Docs Drift

- `README.md` still says the first-party creator index is SQLite and documents `CREATOR_SCOUT_DB=data/creator_scout.sqlite3`, but current `DiscoveryStore` requires InsForge URL/key env vars and uses InsForge REST.
- `task.md` marks "Brand crawl service (Firecrawl/TinyFish/custom)" complete, but the current brand scan path uses the custom `BrandCrawler`; Firecrawl and TinyFish are provider adapters for creator/profile data, not the brand crawler.
- `implementation_plan.md` proposes a dark neon/glassmorphism redesign that conflicts with the current Sticker Notebook design system.
- `creator-scout-technical-spec.md` includes many production recommendations that are not implemented, including LangGraph, Dodo, AutoSend, Redis, agent run logs, and browser fallback.

### Discovery Gaps

- Campaign creation uses one provider for all generated queries, defaulting to `youtube`; the current UI also hardcodes `provider: "youtube"` when launching a campaign.
- Instagram and TikTok are visible platform choices, but there is no official ingestion adapter for either platform.
- TinyFish query discovery creates shallow records from search results. TinyFish Fetch is only used for explicit URLs.
- Firecrawl cannot discover creators from a query.
- Public web cannot discover creators from a query.
- Shortlist generation uses the cached/indexed creators in InsForge. Queued provider jobs must be processed by the worker before fresh results can affect ranking.
- Brand crawler fetch failures produce a synthesized fallback page and heuristic brief. This is useful for demos, but fallback confidence and provenance should be surfaced more explicitly to users.

### Architecture Gaps

- LangGraph and the multi-agent workflow are in the technical spec only; the implemented workflow is deterministic Python services plus a polling worker.
- The worker is a local/CLI polling process, not a deployed or managed background service.
- There is no Redis-backed rate limiting, queue, or provider concurrency control.
- There are no durable checkpoints beyond `discovery_jobs` status/output/error fields.
- Retry support is limited to marking a failed job queued again; there is no full retry policy with attempt counts, backoff metadata, or dead-letter handling in the schema.
- `docs/insforge_audit.md` says the new `creatorScout` InsForge project may need schema/env verification. The linked project, env files, and deployed schema should be rechecked before relying on production data.

### Product Gaps

- Outreach drafts exist, but there is no compliant sending workflow.
- There is no unsubscribe, suppression list, bounce handling, sender verification, Gmail OAuth sending, or AutoSend integration.
- CRM board state is frontend-lite. Status changes are local state updates in the current page flow and are not persisted by the UI handler.
- CSV export is browser-side Blob generation. There is no InsForge Storage persistence for exports or campaign snapshots.
- Billing through Dodo/Stripe is not implemented.
- Lifecycle/product email automation through AutoSend is not implemented.
- Contact enrichment is basic public email extraction from allowed public text, not a full enrichment/verifier workflow.

### Data And Compliance Gaps

- RLS/security hardening is not documented as complete. The current schema grants broad table privileges to anon, authenticated, and project_admin roles.
- Provider request logging exists in `provider_requests`, but TinyFish run IDs/browser metadata are not stored because Browser/Agent APIs are not used.
- Contact provenance is stored through contacts and sources, but there is no suppression/do-not-contact workflow beyond the `do_not_contact` contact field.
- Restricted social domains are blocked for public fetches, but product copy and UI should avoid implying direct Instagram/TikTok/LinkedIn scraping.

## Verification Notes

The current-state assertions above were checked against local files with targeted searches for:

- `tinyfish`, `firecrawl`, `youtube`, `provider`
- `BrandCrawler`
- `LangGraph`
- `Modash`
- `SQLite`
- `RLS`
- `run_id`, `browser`, `agent`

No tests are required for this document-only change. Running the Python tests may require valid InsForge environment variables and network access because `DiscoveryStore` initializes against InsForge.
