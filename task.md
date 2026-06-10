# Creator Scout AI — Current MVP Tasks

## 1. Foundation
- [x] Create InsForge Postgres tables (full schema)
- [x] Initialize Next.js app in `apps/web/`
- [x] Configure InsForge SDK client
- [x] Set up design system (CSS variables, typography, layout)
- [x] Create shared layout with sidebar navigation
- [x] Set up auth pages (sign-in, sign-up)

## 2. LLM Integration (AI Brain)
- [x] Create AI service layer with InsForge AI gateway
- [x] Implement LLM brand intelligence extraction
- [x] Implement LLM creator scoring (hybrid deterministic + AI)
- [x] Implement outreach draft generation
- [x] Add embeddings for semantic search

## 3. Frontend Screens
- [x] Screen 1: New Campaign
- [x] Screen 2: Brand Intelligence Review
- [x] Screen 3: Creator Strategy
- [x] Screen 4: Ranked Creator Results
- [x] Screen 5: Creator Profile Drawer
- [x] Screen 6: Outreach Composer
- [x] Screen 7: CRM Board (Lite)
- [x] Screen 8: CSV Export

## 4. Backend Services
- [x] Brand crawl service (custom brand crawler)
- [x] Creator discovery pipeline
- [x] Campaign workflow orchestration
- [x] Contact enrichment
- [x] Retry-aware worker queue fields and persisted job summaries

## 5. Integrations
- [x] InsForge Auth (email + Google + GitHub OAuth)
- [x] InsForge Storage (campaign CSV exports)
- [ ] Dodo Payments billing (later)
- [ ] AutoSend lifecycle email (later)

## 6. UI Redesign & Sticker Notebook Theme
- [x] Design warm cream Sticker Notebook theme in `globals.css`
- [x] Implement sassy hero section & landing state in `page.tsx`
- [x] Add tab-based dashboard navigation in `page.tsx`
- [x] Enhance creator drawer with pitch composition, compliance status, and evidence grids
- [x] Add micro-animations & Framer Motion entrance animations

## 7. Backend Stability & Performance Fixes
- [x] Fix bigint overflow: `creator_accounts.follower_count/subscriber_count/avg_views` → bigint
- [x] Add `_safe_count()` in ingest.py to clamp large numbers (PostgREST cache resilience)
- [x] Make `ingest_records()` resilient (per-record error catch, continue on failure)
- [x] Make worker main loop resilient with exponential backoff on job failures
- [x] Add 10s timeout + error swallow on `add_source` (best-effort source indexing)
- [x] Add in-process TTL cache (5 min) for API key lookups to eliminate InsForge round-trips on every request
- [x] Fix HTTP shadowing bug: run worker as `python3 -m creator_scout.discovery.worker`
- [x] Parallel outreach draft generation (ThreadPoolExecutor in service.py)
- [x] Bulk upsert campaign_creators in single HTTP payload
- [x] Deduplication of FK IDs in store._request to eliminate 90+ redundant calls per insert
- [x] Prefer server-only `INSFORGE_API_BASE_URL` / `INSFORGE_API_KEY`
- [x] Persist CRM status, pitch, and notes updates
- [x] Persist CSV export metadata in InsForge

## Current Discovery Limits
- YouTube is the default live query-discovery provider.
- TinyFish can be selected explicitly for allowed public search-result discovery.
- Firecrawl and `public_web` are explicit URL refresh/enrichment providers.
- Instagram and TikTok are cached/indexed platform filters until official adapters exist.
- Outreach draft generation is in scope; sending email is out of scope until compliance controls are implemented.

## Running Services
- API server: `PYTHONPATH=. python3 -u apps/api/main.py` -> http://127.0.0.1:8765
- Web app: `npm run dev` in `apps/web/` -> http://localhost:3000
- Worker: `PYTHONPATH=. python3 -u -m creator_scout.discovery.worker --loop --interval 30`
