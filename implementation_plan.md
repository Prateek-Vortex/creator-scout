# Creator Scout Implementation Plan

`docs/current_state_and_gaps.md` is the current-state source of truth. This file replaces the older dark/neon UI redesign plan, which is obsolete.

## Active Direction

- Keep the warm cream Sticker Notebook UI defined in `DESIGN_SYSTEM.md` and `.gemini/ui-skills.md`.
- Use InsForge as the only backend store.
- Run API, web, and worker as separate processes locally.
- Keep YouTube as the default query-discovery provider.
- Keep TinyFish as an explicit allowed public search-result discovery provider.
- Keep Firecrawl and `public_web` for explicit URL refresh/enrichment.
- Do not add unauthorized Instagram, TikTok, LinkedIn, or Facebook scraping.

## Current Priorities

1. Stabilize campaign UX around queued/running discovery jobs.
2. Harden InsForge schema, grants, RLS posture, and server-only env handling.
3. Run one managed discovery worker with retry/backoff fields.
4. Persist CRM edits and CSV export metadata.
5. Keep outreach sending out of scope until suppression, unsubscribe, sender verification, and compliance controls exist.

## Verification

- Audit live InsForge schema before migration.
- Apply schema changes on an InsForge branch first.
- Smoke-test API auth, campaign reads, job summaries, shortlist building, CRM persistence, and export persistence before merging backend changes to the parent project.
