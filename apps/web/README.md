# Creator Scout Web

Next.js dashboard for the Creator Scout AI Phase 1 MVP. The UI uses the warm cream Sticker Notebook design system from the repo root docs.

## Local Environment

Create `apps/web/.env.local` with:

```bash
NEXT_PUBLIC_CREATOR_SCOUT_API_URL=http://127.0.0.1:8765
NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN=<demo-api-key-from-python-seed>
NEXT_PUBLIC_INSFORGE_URL=https://<your-insforge-project>.ap-southeast.insforge.app
NEXT_PUBLIC_INSFORGE_ANON_KEY=<insforge-anon-key>
```

Only public browser/auth values belong in `NEXT_PUBLIC_*`. Do not put `INSFORGE_API_KEY` in this file.

The Python API and worker run as separate processes and require server-only env vars in their own shell or root `.env`:

```bash
INSFORGE_API_BASE_URL=https://<your-insforge-project>.ap-southeast.insforge.app
INSFORGE_API_KEY=<server-api-key>
YOUTUBE_API_KEY=<youtube-api-key>
TINYFISH_API_KEY=<optional-tinyfish-key>
FIRECRAWL_API_KEY=<optional-firecrawl-key>
AUTOSEND_API_KEY=<optional-autosend-key>
AUTOSEND_FROM_EMAIL=<verified-sender@example.com>
AUTOSEND_FROM_NAME=Creator Scout
AUTOSEND_REPLY_TO_EMAIL=<optional-reply-to@example.com>
AUTOSEND_UNSUBSCRIBE_GROUP_ID=<required-for-outreach-send>
```

## Run

From `apps/web`:

```bash
npm run dev
```

Open `http://localhost:3000`.

The dashboard includes the MVP flow: new campaign, brand brief review, creator
strategy, ranked results, profile drawer, outreach composer, CRM board, and CSV
export. Campaign creation queues discovery jobs; fresh provider results appear
after the separate worker processes queued/running jobs.
