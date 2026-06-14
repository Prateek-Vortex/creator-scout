# Creator Scout

Creator Scout is an InsForge-backed creator discovery and campaign shortlisting app. The current product state is documented in [`docs/current_state_and_gaps.md`](docs/current_state_and_gaps.md); use that document as the canonical reference when older PRD/spec files disagree.

## Current Architecture

- Python API: `apps/api/main.py`, serving `/v1/*` on `http://127.0.0.1:8765`.
- Web app: `apps/web`, a Next.js Sticker Notebook UI.
- Backend: InsForge Postgres, Storage, Auth, and AI gateway for project `creatorScout`.
- Worker: `python -m creator_scout.discovery.worker --loop --interval 30`.
- Query discovery: YouTube by default through the official YouTube Data API.
- TinyFish: explicit alternative for allowed public search-result discovery.
- Firecrawl and `public_web`: explicit URL refresh/enrichment only.

Instagram and TikTok are supported as cached/indexed platform filters in the current UI and search model. This repo does not implement unauthorized Instagram, TikTok, LinkedIn, or Facebook scraping.

## Required Environment

**Forking?** Spin up your own InsForge project in ~2 minutes:

```bash
npx @insforge/cli login --user-api-key <your-user-key>   # one-time
npx @insforge/cli link --project-id <your-project-id>    # links this repo to your project
```

The `<your-insforge-project>` placeholder in the env snippets below becomes the `appkey` of the project you just linked. The CLI writes `.insforge/project.json` for you (gitignored).

Server-side Python processes require server-only InsForge credentials:

```bash
INSFORGE_API_BASE_URL=https://<your-insforge-project>.ap-southeast.insforge.app
INSFORGE_API_KEY=...
YOUTUBE_API_KEY=...
TINYFISH_API_KEY=...
FIRECRAWL_API_KEY=...
```

The browser app uses only public client config and the Creator Scout API token:

```bash
# apps/web/.env.local
NEXT_PUBLIC_CREATOR_SCOUT_API_URL=http://127.0.0.1:8765
NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN=...
NEXT_PUBLIC_INSFORGE_URL=https://<your-insforge-project>.ap-southeast.insforge.app
NEXT_PUBLIC_INSFORGE_ANON_KEY=...
```

Do not expose `INSFORGE_API_KEY` through any `NEXT_PUBLIC_*` variable.

## Run Locally

Start the API:

```bash
PYTHONPATH=. python3 -u apps/api/main.py
```

Start the web app:

```bash
cd apps/web
npm run dev
```

Start the discovery worker in a separate process:

```bash
PYTHONPATH=. python3 -u -m creator_scout.discovery.worker --loop --interval 30
```

Create a demo API key when needed:

```bash
PYTHONPATH=. python3 -m creator_scout.discovery.seed
```

## API Surface

Implemented now:

```text
POST /v1/discovery/search
POST /v1/brand-scans
GET  /v1/brands/{brand_id}
POST /v1/campaigns
GET  /v1/campaigns/{campaign_id}
POST /v1/campaigns/{campaign_id}/shortlist
GET  /v1/campaigns/{campaign_id}/creators
PATCH /v1/campaigns/{campaign_id}/creators/{creator_id}
POST /v1/campaigns/{campaign_id}/export
GET  /v1/creators/{creator_id}
POST /v1/discovery/refresh
POST /v1/discovery/ingest-query
GET  /v1/jobs/{job_id}
POST /v1/jobs/{job_id}/retry
GET  /v1/usage
GET  /health
```

Create a campaign:

```bash
curl -s http://127.0.0.1:8765/v1/campaigns \
  -H "Authorization: Bearer <demo-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_url": "https://brand.example",
    "geo": "India",
    "goal": "ugc",
    "provider": "youtube",
    "platforms": ["youtube", "instagram", "tiktok"],
    "query_limit": 5,
    "per_query_limit": 10
  }'
```

Campaign creation queues discovery jobs. Fresh provider results appear only after the worker processes those jobs. Build the shortlist after queued/running jobs finish:

```bash
curl -s http://127.0.0.1:8765/v1/campaigns/<campaign_id>/shortlist \
  -H "Authorization: Bearer <demo-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"limit": 25}'
```

## Managed Worker

`Dockerfile.worker` builds a worker image with the default command:

```bash
python -m creator_scout.discovery.worker --loop --interval 30
```

Required runtime env:

- `INSFORGE_API_BASE_URL`
- `INSFORGE_API_KEY`
- `YOUTUBE_API_KEY` for YouTube query discovery
- `TINYFISH_API_KEY` when using TinyFish discovery
- `FIRECRAWL_API_KEY` when using explicit Firecrawl URL refresh
- `AUTOSEND_API_KEY`, `AUTOSEND_FROM_EMAIL`, and `AUTOSEND_UNSUBSCRIBE_GROUP_ID` for explicit outreach sends

Deploy one worker instance initially to avoid distributed queue-locking complexity.

## Core Rule

Discovery is the product moat. Competitor APIs such as Modash are benchmarks, not dependencies. Grow the index through allowed public web sources, official APIs, creator opt-in, user imports, creator-owned pages/media kits, and refresh jobs with strict budget and compliance controls.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
