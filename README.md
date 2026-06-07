# Creator Scout

Backend-first scaffold for the Creator Scout discovery moat.

This first cut builds the core discovery system without external Python dependencies:

- First-party creator index in SQLite.
- Creator/account/contact/source data contracts.
- Public Discovery API contracts under `/v1`.
- Exact profile lookup before semantic-ish ranked search.
- Evidence, freshness, confidence, and missing fields in responses.
- Developer API keys, credit ledger, and usage events.
- Real ingestion adapter skeletons for YouTube, public web, TinyFish, and Firecrawl.
- Refresh job queue and worker runner.
- Brand-led campaign orchestration: scan a brand, generate search queries, queue discovery jobs, and build a scored shortlist.
- Seed data for YouTube, Instagram, TikTok, newsletter, Pinterest, Twitch, and X-style creator records.

## Run Locally

Use the bundled Codex Python runtime or any Python 3.11+:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m creator_scout.discovery.seed
```

The seed command prints a demo API key. Then run:

```bash
CREATOR_SCOUT_DB=data/creator_scout.sqlite3 /Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 apps/api/server.py
```

Search:

```bash
curl -s http://127.0.0.1:8765/v1/discovery/search \
  -H "Authorization: Bearer <demo-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Indian acne safe moisturizer skincare creator",
    "platforms": ["instagram", "youtube"],
    "locations": ["India"],
    "languages": ["hi", "en"],
    "topics": ["skincare", "acne", "moisturizer"],
    "follower_min": 5000,
    "follower_max": 100000,
    "limit": 5
  }'
```

Usage:

```bash
curl -s http://127.0.0.1:8765/v1/usage \
  -H "Authorization: Bearer <demo-api-key>"
```

Queue a creator refresh:

```bash
curl -s http://127.0.0.1:8765/v1/discovery/refresh \
  -H "Authorization: Bearer <demo-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"profile_url":"https://example.com/media-kit","provider":"public_web"}'
```

Scan a brand URL and generate creator-search queries:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.brand.scan https://brand.example \
  --geo India \
  --goal ugc \
  --enqueue-discovery \
  --provider youtube
```

Create a campaign from a brand URL, queue YouTube discovery jobs, and optionally build a shortlist from the current index:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.campaign.create https://brand.example \
  --geo India \
  --goal ugc \
  --provider youtube \
  --platform youtube \
  --platform instagram \
  --platform tiktok \
  --shortlist
```

Run one queued refresh job:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m creator_scout.discovery.worker
```

Grow the index from a YouTube query:

```bash
YOUTUBE_API_KEY=<key> /Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.discovery.ingest_query "skincare India acne routine" \
  --provider youtube \
  --limit 10
```

Only enqueue the query and let the worker process it:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.discovery.ingest_query "skincare India acne routine" \
  --provider youtube \
  --limit 10 \
  --enqueue-only
```

Queue a batch of index-growth queries:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.discovery.seed_queries \
  --queries data/seed_queries.json
```

Run a scheduled worker loop:

```bash
/Users/prateeksaxena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m creator_scout.discovery.worker \
  --loop \
  --interval 30
```

Optional provider env vars:

```text
YOUTUBE_API_KEY=
TINYFISH_API_KEY=
FIRECRAWL_API_KEY=
```

## Discovery API Surface

Implemented now:

```text
POST /v1/discovery/search
POST /v1/brand-scans
GET  /v1/brands/{brand_id}
POST /v1/campaigns
GET  /v1/campaigns/{campaign_id}
POST /v1/campaigns/{campaign_id}/shortlist
GET  /v1/campaigns/{campaign_id}/creators
GET  /v1/creators/{creator_id}
POST /v1/discovery/refresh
POST /v1/discovery/ingest-query
GET  /v1/jobs/{job_id}
POST /v1/jobs/{job_id}/retry
GET  /v1/usage
GET  /health
```

Implemented ingestion adapters:

```text
youtube: official YouTube Data API channel search/profile hydration
public_web: robots-aware fetch for creator-owned sites/media kits
tinyfish: Search/Fetch wrapper for allowed public pages
firecrawl: Scrape wrapper for allowed public pages
```

Campaign API example:

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

```bash
curl -s http://127.0.0.1:8765/v1/campaigns/<campaign_id>/shortlist \
  -H "Authorization: Bearer <demo-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"limit": 25}'
```

Planned next:

```text
POST /v1/discovery/semantic-search
POST /v1/discovery/lookalikes
POST /v1/creators/batch
GET  /v1/creators/{creator_id}/report
GET  /v1/creators/{creator_id}/audience
GET  /v1/creators/{creator_id}/collaborations
POST /v1/contact/lookup
```

## Core Rule

Discovery is our moat, so competitor APIs such as Modash are benchmarks, not dependencies. The engine should grow through allowed public web sources, official APIs where available, creator opt-in, user imports, creator-owned pages/media kits, and refresh jobs with strict budget and compliance controls.
