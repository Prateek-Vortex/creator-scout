# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of Truth

When older PRD/spec files (`creator-scout-product-prd.md`, `creator-scout-technical-spec.md`) disagree with the code, **prefer `docs/current_state_and_gaps.md` plus the code in `apps/api`, `apps/web`, and `creator_scout/`**. The older spec describes LangGraph and a full multi-agent workflow; only parts of that are actually implemented (see Architecture below).

## Run Locally (three separate processes)

```bash
# API (FastAPI on 127.0.0.1:8765)
PYTHONPATH=. python3 -u apps/api/main.py

# Web app (Next.js on :3000, proxies /api/* to the Python API)
cd apps/web && npm run dev

# Discovery worker (polls InsForge for queued jobs)
PYTHONPATH=. python3 -u -m creator_scout.discovery.worker --loop --interval 30
```

Always run Python commands with `PYTHONPATH=.` from the repo root — `apps/api/main.py` and `creator_scout/*` import each other as siblings via this path.

Seed a demo API key for local development:

```bash
PYTHONPATH=. python3 -m creator_scout.discovery.seed
```

Frontend lint/build:

```bash
cd apps/web && npm run lint
cd apps/web && npm run build
```

There is no Python test suite currently — the previous `tests/` directory is deleted (visible in `git status`). Do not re-add test files unless the user asks; do not assume `pytest` will work.

## Environment

Server-side processes (API and worker) read these from `.env`:

- `INSFORGE_API_BASE_URL`, `INSFORGE_API_KEY` — server-only InsForge credentials
- `YOUTUBE_API_KEY` — required for the default discovery provider
- `TINYFISH_API_KEY`, `FIRECRAWL_API_KEY` — optional alternative adapters
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `OAUTH_TOKEN_ENCRYPTION_KEY`, `WEB_APP_URL` — Gmail OAuth (per-user outreach sending). `OAUTH_TOKEN_ENCRYPTION_KEY` is a Fernet key (`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Replaces the previous shared AutoSend mailbox.
- `INSFORGE_DB_URL` / `DATABASE_URL` / `POSTGRES_URL` — direct Postgres URL used by the LangGraph `PostgresSaver` checkpointer; if unset, the graph falls back to `MemorySaver` (dev only)
- `CREATOR_SCOUT_WORKER_CONCURRENCY` (default 3) — how many discovery jobs the worker processes in parallel in `--loop` mode
- `TINYFISH_AGENT_ENABLED` (default true) and `TINYFISH_AGENT_MAX_LISTICLES_PER_QUERY` (default 3) — when on, TinyFish search results that look like creator listicles are routed through TinyFish's Agent API to extract per-creator rows (Instagram / TikTok / X / Twitch handles) instead of being ingested as a single `platform=website` row

The browser reads only `NEXT_PUBLIC_*` keys (`NEXT_PUBLIC_CREATOR_SCOUT_API_URL`, `NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN`, `NEXT_PUBLIC_INSFORGE_URL`, `NEXT_PUBLIC_INSFORGE_ANON_KEY`). **Never expose `INSFORGE_API_KEY` through a `NEXT_PUBLIC_*` variable.**

## Architecture

### Backend: InsForge-only persistence

`creator_scout/discovery/store.py` is the single persistence layer. All data goes through InsForge REST endpoints — `/api/database/records/{table}`, `/api/ai/embeddings`, `/api/ai/chat/completion`, `/api/storage/*`. There is a `data/creator_scout.sqlite3` left over from earlier scaffolding, but the live code path does not use it — treat InsForge as the only backend store. UUIDs from non-UUID IDs are deterministically generated via `to_uuid()` (`uuid5(NAMESPACE_DNS, val)`).

### Two parallel execution paths

The codebase contains **two overlapping orchestration systems**. Know which one a route is using before making changes:

1. **Deterministic services + polling worker** (`apps/api/main.py` + `creator_scout/discovery/service.py`, `campaign/service.py`, `brand/service.py`). This is what the current web UI primarily drives. Campaign creation queues `creator_discovery_query` jobs into InsForge `discovery_jobs`; the worker (`creator_scout/discovery/worker.py`) polls and processes them. The UI blocks "Build shortlist" while queued/running jobs remain.

2. **LangGraph campaign graph** (`creator_scout/graph/` + `apps/api/graph_routes.py`). Routes live under `/v1/graph/*`. The compiled graph (`graph.py`) uses `interrupt_before` HIL gates at `query_planner_node`, `outreach_draft_node`, and `send_outreach_node`. Checkpoints persist via `PostgresSaver` against InsForge Postgres. The frontend polls run status and consumes `/v1/graph/run/{id}/stream` (SSE) for brand-scan token streaming. Realtime pause notifications are broadcast on the `graph_runs:%` channel (registered by migration `20260614084300_realtime-channels.sql`).

If you add a new node to the LangGraph workflow, update `graph.py` (node list, edges, interrupt list) and `graph/state.py`. Nodes wrap existing services in `creator_scout/`; do not put new business logic in nodes.

### Discovery adapters

`creator_scout/discovery/adapters/factory.py` picks a provider:

- `youtube` (default for query discovery) — official YouTube Data API
- `tinyfish` — explicit allowed public search-result discovery (Search + Fetch). Search results that look like listicles can additionally be sent to TinyFish's Agent API (`creator_scout/discovery/adapters/agent_extract.py`) to extract per-creator handles; gated by `TINYFISH_AGENT_ENABLED`.
- `firecrawl` / `public_web` — **explicit-URL refresh/enrichment only**; their `discover()` raises
- `tavily`, `exa` — alt search providers

`creator_scout/discovery/compliance.py` blocks fetches against Instagram, TikTok, LinkedIn, Facebook, and gated/login paths. Instagram/TikTok appear as UI platform filters and normalized account platforms — but **this repo has no ingestion adapter for them and must not gain one**. Do not write code that scrapes those platforms or implies it does in product copy.

### API surface (FastAPI)

`apps/api/main.py` mounts core routes (`/v1/discovery/*`, `/v1/brands/*`, `/v1/campaigns/*`, `/v1/creators/*`, `/v1/jobs/*`, `/v1/usage`, `/health`) and includes `graph_routes.router` for `/v1/graph/*`. Auth is API-key based via `Authorization: Bearer ...` or `x-api-key:`; `/v1/graph/run/*/stream` additionally accepts `?api_key=` because `EventSource` can't set headers. Exception handlers map `PermissionError → 402`, `ValueError → 400`, `RuntimeError → 500` (or 503 if message contains `"InsForge"`).

### Web app: Sticker Notebook UI

`apps/web/` is Next.js 16 (App Router) + React 19 + Framer Motion + Tailwind 4 + `@insforge/sdk`. `next.config.ts` rewrites `/api/v1/*` → the Python API. `apps/web/src/lib/api.ts` is the typed client; `apps/web/src/lib/insforge.ts` is the browser auth client.

**Before any UI change, read `DESIGN_SYSTEM.md` and `.gemini/ui-skills.md`.** The theme is the warm cream "Sticker Notebook" system (`#faf9f6` background, paper surfaces, sticker cards, Framer Motion entrances, Caveat handwriting accents, 4 badge colors: coral/teal/lavender/amber). The older dark/neon redesign plan is obsolete — do not re-introduce it unless the user explicitly asks. Use CSS classes from `globals.css` (`.sticker-card`, `.notebook-page`, `.badge-sticker`, `.glow-btn-accent`) rather than ad-hoc styles or Tailwind preset colors like `bg-blue-500`.

### Migrations

`migrations/` holds timestamped `.sql` files applied via InsForge CLI. The repo's working pattern is to apply on an InsForge branch first (e.g. `mvp-hardening`), smoke-test, then merge to the parent project. See `docs/insforge_branch_verification_2026-06-07.md`.

## InsForge Skills

This project uses InsForge. Reach for the installed skills (`insforge`, `insforge-cli`, `insforge-debug`, `insforge-integrations`) before implementing any InsForge feature — don't guess the API. Key patterns: inserts take an array (`insert([{...}])`); reference users with `auth.users(id)` and `auth.uid()` in RLS; for storage uploads, persist both the returned `url` and `key`.
