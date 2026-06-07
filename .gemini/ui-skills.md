# Creator Scout — UI Development Skills

This file tells coding agents how to build and modify the Creator Scout web frontend.
**Read `DESIGN_SYSTEM.md` at the project root before making any UI changes.**

---

## Tech Stack

| Layer | Technology | Config |
|-------|-----------|--------|
| Framework | Next.js 16 (App Router) | `apps/web/next.config.ts` |
| Language | TypeScript (strict) | `apps/web/tsconfig.json` |
| Styling | Tailwind CSS 4 + Vanilla CSS | `apps/web/src/app/globals.css` |
| Animation | Framer Motion 12 | Installed in `apps/web/package.json` |
| Fonts | Geist, Geist Mono, Caveat | `apps/web/src/app/layout.tsx` |
| Backend SDK | @insforge/sdk | `apps/web/src/lib/insforge.ts` |
| API Client | Custom fetch wrapper | `apps/web/src/lib/api.ts` |

---

## Project Structure

```
apps/web/
├── src/
│   ├── app/
│   │   ├── globals.css        ← Design system tokens & utility classes
│   │   ├── layout.tsx         ← Root layout, fonts, meta tags
│   │   ├── page.tsx           ← Main app (landing + workspace)
│   │   ├── sign-in/page.tsx   ← Auth pages
│   │   └── sign-up/page.tsx
│   └── lib/
│       ├── api.ts             ← API client, TypeScript interfaces
│       └── insforge.ts        ← InsForge SDK client singleton
├── next.config.ts             ← API proxy rewrites
├── package.json
└── .env.local                 ← API keys (never commit)
```

---

## Key Files to Read Before Any UI Change

1. **`DESIGN_SYSTEM.md`** (project root) — Complete visual language reference: colors, typography, surfaces, components, animations, anti-patterns
2. **`globals.css`** — All CSS classes (`.sticker-card`, `.notebook-page`, `.badge-sticker`, `.glow-btn`, etc.)
3. **`page.tsx`** — Main monolithic component containing:
   - `LandingPage` component (public-facing)
   - `Workspace` component (after campaign creation)
   - Helper components: `Field`, `PlatformPill`, `MetricCard`, `ChipList`, `Avatar`, `Navbar`
   - Root `Home` component with state management
4. **`api.ts`** — All TypeScript interfaces (`Campaign`, `CampaignCreator`, `CreatorProfile`, etc.) and API methods

---

## Design Aesthetic: "Sticker Notebook"

The UI follows a **physical sticker/notebook** metaphor:
- **Warm cream background** (`#faf9f6`) — never dark mode
- **Paper-like surfaces** — `.notebook-page` (stacked paper shadow), `.sticker-card` (Polaroid with rotation)
- **Vibrant badge stickers** — `.badge-sticker` with 4 color variants (coral/teal/lavender/amber)
- **Handwriting accent** — Caveat font for 1–3 personality words in headings
- **Subtle micro-animations** — Framer Motion scroll parallax, floating badges, hover straightening

**Full design reference**: [DESIGN_SYSTEM.md](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/DESIGN_SYSTEM.md)

---

## How to Add a New Component

1. **Check `DESIGN_SYSTEM.md`** for the correct colors, typography, and surface class
2. **Use existing CSS classes** from `globals.css` — don't create ad-hoc styles
3. **Follow the helper component pattern** from `page.tsx`:
   ```tsx
   function MyComponent({ label, value }: { label: string; value: string }) {
     return (
       <div className="rounded-xl border border-[#e8e4df] bg-white p-5">
         <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">{label}</p>
         <p className="mt-2 text-base font-medium text-ink">{value}</p>
       </div>
     );
   }
   ```
4. **Add motion** with Framer Motion for entrances:
   ```tsx
   <motion.div
     initial={{ opacity: 0, y: 12 }}
     animate={{ opacity: 1, y: 0 }}
     transition={{ duration: 0.4 }}
   >
   ```

---

## How to Add a New Page/Route

1. Create `apps/web/src/app/my-page/page.tsx`
2. Import the design system: reuse helper components from `page.tsx` or extract them into `src/components/`
3. Use `notebook-page` for main content containers
4. Use the standard layout: `bg-[#faf9f6]` background, `max-w-5xl mx-auto px-6 py-8`
5. Add to navbar if needed

---

## How to Add a New Tab to the Workspace

The workspace uses a simple tab state in `page.tsx`:

1. Add the tab ID to the `ActiveTab` type union
2. Add an entry to the `TABS` array in the `Workspace` component
3. Add a conditional rendering block: `{activeTab === "mytab" && ( ... )}`
4. Wrap content in `<motion.div>` with the standard entrance animation

---

## Framer Motion Patterns

### Scroll-linked (hero section)
```tsx
const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
const heroScale = useTransform(scrollYProgress, [0, 0.8], [1, 0.95]);
const smoothOpacity = useSpring(heroOpacity, { stiffness: 80, damping: 20 });
```

### Stagger on scroll reveal
```tsx
<motion.div
  initial={{ opacity: 0, y: 40 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true, amount: 0.3 }}
  transition={{ delay: index * 0.12, duration: 0.5 }}
>
```

### Floating element
```tsx
<motion.div
  animate={{ y: [0, -8, 0], rotate: [-3, -1, -3] }}
  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
>
```

---

## Color Usage Quick Reference

| Purpose | Color | Class/Value |
|---------|-------|-------------|
| Page background | `#faf9f6` | `bg-[#faf9f6]` |
| Card/panel background | `#ffffff` | `bg-white` |
| Hover background | `#f8f6f2` | `bg-[#f8f6f2]` |
| Active tab background | `#f3f0eb` | `bg-[#f3f0eb]` |
| Section alt background | `#f5f2ed` | `bg-[#f5f2ed]` |
| Primary text | `#1a1a1a` | `text-ink` |
| Secondary text | `#7a7a7a` | `text-[#7a7a7a]` |
| Faint text | `#b5afa6` | `text-[#b5afa6]` |
| Borders | `#e8e4df` | `border-[#e8e4df]` |
| Hover borders | `#d4cfc8` | `border-[#d4cfc8]` |
| Primary CTA | `#e85d4a` | `.glow-btn-accent` |
| Secondary CTA | `#1a1a1a` | `.glow-btn` |

---

## API Integration

### Python backend (runs separately)
```bash
python apps/api/server.py   # Starts on http://127.0.0.1:8765
```

### Next.js proxy
`next.config.ts` rewrites `/api/v1/*` → `http://127.0.0.1:8765/v1/*`

### API client usage
```tsx
import { api } from "@/lib/api";

// Create campaign (simplified — only URL needed)
const res = await api.createCampaign({ brand_url, goal: "ugc", geo: "India", platforms: ["youtube", "instagram", "tiktok"] });

// Build shortlist
const res = await api.buildShortlist(campaignId, { limit: 30 });
```

### Key TypeScript interfaces (in `api.ts`)
- `Campaign` — campaign data with brief, queries, jobs
- `CampaignBrief` — extracted brand intelligence
- `CampaignCreator` — scored creator with profile, pitch, outreach draft
- `CreatorProfile` — creator data with accounts, contacts, sources

---

## Common Mistakes to Avoid

1. **Using dark mode colors** — This is a light cream theme. No `bg-black`, `text-white` on dark surfaces
2. **Using Tailwind preset colors** — Use semantic tokens from `globals.css`, not `bg-blue-500`
3. **Skipping animations** — Every new panel/section should have a Framer Motion entrance
4. **Using `<img>` without alt** — Always provide meaningful alt text
5. **Hardcoding API URLs** — Use the `api` client from `@/lib/api`
6. **Creating inline styles for colors** — Use the CSS classes defined in `globals.css`
7. **Adding new fonts** — Stick with Inter, JetBrains Mono, and Caveat unless explicitly requested
