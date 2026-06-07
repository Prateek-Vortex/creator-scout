# InsForge Project Setup — Audit & Available Features

## ✅ What Was Done

| Step | Status |
|------|--------|
| Login with API key | ✅ Authenticated as `prateeksaxena733mole@gmail.com` |
| Link to new project | ✅ Linked to **creatorScout** (`4c454309-a451-4184-a812-1e807739cdac`) |
| Agent skills installed | ✅ `insforge`, `insforge-cli`, `insforge-debug`, `insforge-integrations`, `find-skills` |
| `AGENTS.md` updated | ✅ Updated to reference new project |

---

## 🔄 Project Change — Old vs New

| Field | Old Project (AiContentScout) | New Project (creatorScout) |
|-------|-----|-----|
| Project ID | `7eed9783-2018-47da-b110-fa181b8f382e` | `4c454309-a451-4184-a812-1e807739cdac` |
| Appkey | `y9tqgph3` | `ffqsewe5` |
| API Base URL | `https://y9tqgph3.ap-southeast.insforge.app` | `https://ffqsewe5.ap-southeast.insforge.app` |
| Region | `ap-southeast` | `ap-southeast` (same) |
| Org ID | `e1e3e5a6-6d57-4600-9eb0-928e00f3bbf7` | `e1e3e5a6-6d57-4600-9eb0-928e00f3bbf7` (same) |

> [!WARNING]
> **The new project has an empty database** (0 tables). The old project (`y9tqgph3`) had all your existing tables (creators, campaigns, brands, etc.) and data. You need to re-create the schema on the new project.

> [!IMPORTANT]
> **Environment variables still point to the OLD project!** These files need updating:
> - [.env](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/.env) — `NEXT_PUBLIC_INSFORGE_URL` and `NEXT_PUBLIC_INSFORGE_ANON_KEY`
> - [apps/web/.env.local](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/.env.local) — Same vars
> - [.env.example](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/.env.example) — URL reference

---

## 🧰 Available InsForge Features

Here's everything the new **creatorScout** project can use:

### 1. 🗄️ Database (Postgres)
| Feature | Status | Notes |
|---------|--------|-------|
| Tables | ⚠️ Empty | Need to migrate schema from old project |
| RLS Policies | — | Set up row-level security after creating tables |
| Database Functions (RPC) | — | e.g., `match_creators` for semantic search |
| Migrations | ✅ CLI support | `insforge db migrations` |
| Direct SQL | ✅ | `insforge db query "<SQL>"` |
| Import/Export | ✅ | Export schema from old, import into new |

**CLI:** `insforge db query`, `db tables`, `db import`, `db export`

### 2. 🔐 Authentication
| Feature | Status |
|---------|--------|
| Email/Password | ✅ Enabled |
| Google OAuth | ✅ Configured |
| GitHub OAuth | ✅ Configured |
| Email verification | ✅ Required (code-based) |
| Signup | ✅ Enabled |

**Already implemented in code:** [sign-in/page.tsx](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/sign-in/page.tsx), [sign-up/page.tsx](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/sign-up/page.tsx)

### 3. 🤖 AI Model Gateway
| Feature | Status | Notes |
|---------|--------|-------|
| Completions | ✅ Available | Route via `/api/ai/completions` |
| Embeddings | ✅ Available | Route via `/api/ai/embeddings` |
| Models | OpenRouter gateway | GPT-4, Claude, etc. |

**Already implemented in code:** [brand/brief.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/brand/brief.py) (AI brand brief extraction), [store.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/discovery/store.py) (embeddings + semantic search)

### 4. 🚀 Deployments (Vercel)
| Feature | Status |
|---------|--------|
| Frontend deploy | ✅ Available |
| Custom slug | Not configured |
| Env var management | ✅ Available |

**CLI:** `insforge deployments deploy`, `deployments list`, `deployments env`

### 5. ⚡ Edge Functions
| Feature | Status |
|---------|--------|
| Runtime | ✅ Running |
| Functions deployed | 0 |

**CLI:** `insforge functions deploy`, `functions list`, `functions invoke`

### 6. 📦 Storage
| Feature | Status |
|---------|--------|
| Buckets | 0 created |
| Total size | 0 GB |

**From task.md:** Storage for exports/snapshots is marked as TODO.

### 7. 💳 Payments (Stripe)
| Feature | Status |
|---------|--------|
| Stripe integration | ✅ Available |
| Products / Prices | Not configured |
| Subscriptions | Not configured |

**CLI:** `insforge payments config`, `payments sync`, `payments products`

### 8. 🔄 Realtime
| Feature | Status |
|---------|--------|
| WebSocket channels | ✅ Available |

### 9. 📧 Email
| Feature | Status |
|---------|--------|
| SMTP | ❌ Not configured |
| Transactional email | Needs SMTP setup |

### 10. ⏰ Scheduled Tasks (Cron)
| Feature | Status |
|---------|--------|
| Cron jobs | ✅ Available |
| Jobs deployed | 0 |

**CLI:** `insforge schedules create`, `schedules list`

### 11. 🐳 Compute (Docker/Fly.io)
| Feature | Status |
|---------|--------|
| Container deployment | ✅ Available |
| Source or image mode | Both supported |

**CLI:** `insforge compute deploy`, `compute list`

### 12. 📊 PostHog Analytics
| Feature | Status |
|---------|--------|
| Product analytics | ✅ Available |

**CLI:** `insforge posthog`

---

## 📍 Current Code Integration Points

These files reference InsForge and will need the URL/key updated:

| File | What It Does |
|------|-------------|
| [insforge.ts](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/lib/insforge.ts) | SDK client (browser) — reads `NEXT_PUBLIC_INSFORGE_URL` |
| [store.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/discovery/store.py) | Python REST client — reads `NEXT_PUBLIC_INSFORGE_URL` |
| [brief.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/brand/brief.py) | AI completions for brand intelligence |
| [seed.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/discovery/seed.py) | Seed data into Postgres |
| [migrate_db.py](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/creator_scout/discovery/migrate_db.py) | Database migration script |
| [sign-in/page.tsx](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/sign-in/page.tsx) | Auth sign-in (email + OAuth) |
| [sign-up/page.tsx](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/sign-up/page.tsx) | Auth sign-up |

---

## 🎯 Recommended Next Steps

1. **Migrate Database Schema** — Export schema from old project or re-run migration scripts to create all tables on new project
2. **Update Env Vars** — Update `.env`, `apps/web/.env.local` with new project URL + anon key
3. **Set Up Storage Bucket** — Create bucket for CSV exports and campaign snapshots
4. **Deploy Edge Functions** — Move any serverless logic to edge functions
5. **Set Up Stripe** — Configure payment products/prices for billing
6. **Configure SMTP** — Set up transactional emails for auth and outreach
7. **Deploy Frontend** — Use `insforge deployments deploy` to ship the Next.js app to Vercel
