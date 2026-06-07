# AGENTS.md

<!-- INSFORGE:START -->
## InsForge backend

This project uses [InsForge](https://insforge.dev): an all-in-one, open-source Postgres-based backend (BaaS) that gives this app a database, authentication, file storage, edge functions, realtime, an AI model gateway, and payments through one platform.

- **Project:** **creatorScout** (API base `https://ffqsewe5.ap-southeast.insforge.app`)
- **Skills:** these InsForge skills are installed for supported coding agents. Reach for them before implementing any InsForge feature instead of guessing the API:
  - `insforge`: app code with the `@insforge/sdk` client (database CRUD, auth, storage, edge functions, realtime, AI, email, and Stripe payments).
  - `insforge-cli`: backend and infrastructure via the `insforge` CLI (projects, SQL, migrations, RLS policies, storage buckets, functions, secrets, payment setup, schedules, deploys).
  - `insforge-debug`: diagnosing failures (SDK/HTTP errors, RLS denials, auth and OAuth issues) and running security or performance audits.
  - `insforge-integrations`: wiring external auth providers (Clerk, Auth0, WorkOS, Better Auth, etc.) for JWT-based RLS, or the OKX x402 payment facilitator.
  - `find-skills`: discovering additional skills on demand.
- **Credentials:** app code reads keys from `.env.local`; the CLI reads `.insforge/project.json`. Never hardcode or commit keys.

Key patterns:

- Database inserts take an array: `insert([{ ... }])`.
- Reference users with `auth.users(id)`; use `auth.uid()` in RLS policies.
- For storage uploads, persist both the returned `url` and `key`.
<!-- INSFORGE:END -->

## UI / Frontend

The web app (`apps/web/`) uses a **"Sticker Notebook"** design system — warm cream/paper light theme with Framer Motion animations. **Before making any UI changes, read these files:**

- **[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)** — Complete visual language: color palette, typography, CSS surface classes, component patterns, animation system, layout patterns, and anti-patterns
- **[.gemini/ui-skills.md](.gemini/ui-skills.md)** — Technical skills file: tech stack, project structure, how to add components/pages/tabs, Framer Motion patterns, API integration, and common mistakes

Key rules:
- Warm cream background (`#faf9f6`), never dark mode
- Use CSS classes from `globals.css` (`.sticker-card`, `.notebook-page`, `.badge-sticker`, `.glow-btn-accent`)
- Every new panel/section gets a Framer Motion entrance animation
- Fonts: Inter (body), JetBrains Mono (code), Caveat (handwriting accents)
- 4 accent badge colors: coral, teal, lavender, amber
