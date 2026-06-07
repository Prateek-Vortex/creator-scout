# Creator Scout Web

Next.js dashboard for the Creator Scout AI Phase 1 MVP.

## Local Environment

Create `apps/web/.env.local` with:

```bash
NEXT_PUBLIC_CREATOR_SCOUT_API_URL=http://127.0.0.1:8765
NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN=<demo-api-key-from-python-seed>
NEXT_PUBLIC_INSFORGE_URL=https://ffqsewe5.ap-southeast.insforge.app
NEXT_PUBLIC_INSFORGE_ANON_KEY=<insforge-anon-key>
```

The local Python API still owns campaign creation, brand scans, shortlist scoring,
and creator profile reads. InsForge SDK is wired for auth and future database, AI,
and storage integration.

## Run

From `apps/web`:

```bash
npm run dev
```

Open `http://localhost:3000`.

The dashboard includes the MVP flow: new campaign, brand brief review, creator
strategy, ranked results, profile drawer, outreach composer, CRM board, and CSV
export.
