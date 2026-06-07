# Creator Scout — UI Design System Reference

This document defines the visual language for Creator Scout AI.
**Every new UI component, page, or modification must follow these guidelines.**

---

## 1. Design Philosophy: "Sticker Notebook"

The entire UI is built on a **physical sticker/notebook** metaphor:
- Surfaces look like **paper pages**, not flat digital panels
- Interactive elements look like **die-cut stickers** — slightly rotated, casting real shadows
- Accents use a **handwriting font** to simulate scribbled notes
- The palette is **warm and tactile**, not cold digital blue/gray
- **No dark mode.** The theme is exclusively a warm cream/paper light theme
- **No generic AI vibes.** No glowing orbs, neon gradients, dark glassmorphism, or cyber aesthetics

---

## 2. Color Palette

### Foundations (Tailwind theme tokens from `globals.css`)
| Token | Hex | Usage |
|-------|-----|-------|
| `--background` / `cream` | `#faf9f6` | Page background — warm off-white paper |
| `--foreground` / `ink` | `#1a1a1a` | Primary text color |
| `muted` | `#7a7a7a` | Secondary text, labels, placeholders |
| `line` | `#e8e4df` | Borders, dividers, card edges |
| `soft` | `#f3f0eb` | Hover states, subtle backgrounds |
| `panel` | `#ffffff` | Card/panel backgrounds |

### Accents (4 vibrant badge colors)
| Name | Background | Text | Border | CSS Class |
|------|-----------|------|--------|-----------|
| **Coral** | `#fde8e4` | `#c4402d` | `#f5c4ba` | `.badge-coral` |
| **Teal** | `#e0f5f3` | `#1e7a72` | `#b5e5e0` | `.badge-teal` |
| **Lavender** | `#ece4fb` | `#6b4ec0` | `#cebdf5` | `.badge-lavender` |
| **Amber** | `#fdf0db` | `#b07920` | `#f0d9a6` | `.badge-amber` |

### Semantic
| Token | Hex | Usage |
|-------|-----|-------|
| `accent` | `#e85d4a` | Primary CTA buttons, active states |
| `success` | `#3aaa6f` | Positive states, "clean" compliance |
| `warning` | `#e8a33c` | Caution, pending states |
| `danger` | `#d94040` | Errors, risk flags |

### Hard rules
- **Never use** pure black (`#000000`) for backgrounds
- **Never use** pure white (`#ffffff`) for page backgrounds — use `#faf9f6` (cream)
- Cards and panels use `#ffffff` on the cream background for contrast
- Borders are always `#e8e4df` (warm gray), never `#ccc` or `#ddd` (cool gray)

---

## 3. Typography

### Font Stack (configured in `layout.tsx`)
| Purpose | Font | CSS Variable | Weight |
|---------|------|-------------|--------|
| **Body/UI** | Inter (via Geist) | `--font-sans` / `--font-geist-sans` | 400, 500, 600 |
| **Code/Mono** | JetBrains Mono (via Geist Mono) | `--font-mono` / `--font-geist-mono` | 400 |
| **Handwriting accents** | Caveat | `--font-caveat` | 400–700 |

### Usage patterns
- **Section headings**: `text-xl sm:text-2xl font-semibold text-ink tracking-tight`
- **Card labels**: `text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]`
- **Body text**: `text-sm text-[#7a7a7a] leading-relaxed`
- **Mono data**: `text-[10px] font-mono text-[#7a7a7a]`
- **Handwriting accents**: `style={{ fontFamily: "var(--font-caveat)" }}` with `text-accent` or `text-accent-teal`, typically 1 size larger than surrounding text

### Handwriting accent rules
- Use Caveat **only** for 1–3 words that add personality (e.g., "actually fit", "scout?", "nothing you don't")
- Never use it for body text, labels, or data fields
- Pair it with a slightly larger font size than the surrounding heading

---

## 4. Surface Classes (defined in `globals.css`)

### `.notebook-page`
The primary content container. Looks like stacked paper sheets.
```html
<div class="notebook-page p-6">
  <!-- Content here -->
</div>
```
- White background, `border-radius: 16px`
- Layered box-shadow simulating 3 stacked pages behind
- Use for: forms, detail panels, loading cards, empty states

### `.sticker-card`
Polaroid/die-cut sticker element. Slightly elevated, has a subtle peeling corner.
```html
<div class="sticker-card p-6" style="rotate: -2deg">
  <!-- Content here -->
</div>
```
- Pair with `STICKER_ROTATIONS` array for random slight tilts
- On hover: straightens (`rotate(0deg)`), lifts higher, shadow intensifies
- Use for: feature cards, stat blocks, anything "pinned" to the layout

### `.glass-card`
Clean elevated card without sticker effects.
```html
<div class="glass-card p-6">
  <!-- Content here -->
</div>
```
- White background, subtle border, lifts on hover
- Use for: generic list items, generic containers

### `.glass-panel`
Flat panel surface (no hover effects).
```html
<div class="glass-panel rounded-xl p-6">
  <!-- Content here -->
</div>
```

### `.badge-sticker`
Small vibrant pill/tag.
```html
<span class="badge-sticker badge-coral text-[9px]">Claude 4.5</span>
<span class="badge-sticker badge-teal text-[9px]">GDPR</span>
<span class="badge-sticker badge-lavender text-[9px]">pgvector</span>
<span class="badge-sticker badge-amber text-[9px]">category</span>
```
- Always pair with a color variant class
- Use for: platform pills, technology tags, field labels, category markers

---

## 5. Component Patterns (in `page.tsx`)

### `<Field>` — Form field wrapper
- `text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]` label
- Input uses `.glass-input` class

### `<PlatformPill>` — Platform badge
- Maps: YouTube → coral, Instagram → lavender, TikTok → teal, default → amber

### `<MetricCard>` — Data metric display
- Label (uppercase micro) + value (base font semibold)
- `accent` variant uses coral tint background

### `<ChipList>` — Tag cloud in a card
- Card container with array of rounded chips inside
- Variants: `default` (warm gray), `success` (green), `danger` (red)

### `<Avatar>` — User initial circle
- Deterministic color based on `name.length % 4`
- Colors cycle through: coral, teal, lavender, amber
- Sizes: `sm` (32px), `md` (40px), `lg` (56px)

---

## 6. Button Styles

| Class | Look | Use for |
|-------|------|---------|
| `.glow-btn` | Dark `#1a1a1a` bg, cream text | Secondary CTAs, nav actions |
| `.glow-btn-accent` | Coral `#e85d4a` bg, white text | Primary CTAs (Analyze, Run Discovery, Mark Contacted) |

Both buttons have:
- `border-radius: 10px`, `font-weight: 600`
- Hover: lifts 1–2px with shadow increase
- Add `cursor-pointer` in JSX

---

## 7. Animation System

### Framer Motion (for scroll-linked & interactive animations)
```tsx
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
```

**Key patterns used:**
- **Hero scroll parallax**: `useScroll` + `useTransform` on opacity/scale/y
- **Entrance animations**: `initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}`
- **Stagger on scroll**: `whileInView` with `delay: i * 0.12`
- **Floating stickers**: `animate={{ y: [0, -8, 0] }}` with infinite repeat
- **Sticker hover**: `whileHover={{ rotate: 0, y: -6, scale: 1.02 }}`
- **Tab content transitions**: `motion.div` with `initial/animate` on every tab panel

### CSS Animations (for simpler effects)
| Class | Effect | Duration |
|-------|--------|----------|
| `.animate-fade-in-up` | Fade + slide up 12px | 0.5s |
| `.animate-slide-up` | Fade + slide up 24px | 0.6s |
| `.animate-scale-in` | Fade + scale from 0.95 | 0.4s |
| `.animate-float` | Gentle Y bounce | 4s infinite |
| `.animate-shimmer` | Loading shimmer gradient | 2s infinite |
| `.animate-pulse-ring` | Coral ring pulse (loading) | 2s infinite |

### Timing curve
- Standard ease: `cubic-bezier(0.16, 1, 0.3, 1)` (Apple-style spring)
- Used consistently across all transitions

---

## 8. Layout Patterns

### Landing Page
```
┌─────────────────────────────────────┐
│ Navbar (fixed, scroll-blur)         │
├─────────────────────────────────────┤
│ Hero (scroll-linked fade/scale)     │
│   - Badge stickers (floating)       │
│   - Heading + Caveat accent         │
│   - URL-only form (notebook-page)   │
├─────────────────────────────────────┤
│ Stats (rotated sticker-cards)       │
├─────────────────────────────────────┤
│ Features (4× sticker-card grid)     │
├─────────────────────────────────────┤
│ CTA Form (notebook-page, #f5f2ed)   │
├─────────────────────────────────────┤
│ Footer                              │
└─────────────────────────────────────┘
```

### Workspace (Dashboard)
```
┌──────────┬──────────────────────────┐
│ Sidebar  │ Top breadcrumb bar       │
│ (white)  ├──────────────────────────┤
│          │ Tab content area         │
│ Logo     │ (scrollable, cream bg)   │
│ Project  │                          │
│ Tabs     │ Uses:                    │
│          │ - notebook-page          │
│          │ - MetricCard             │
│ New Camp │ - ChipList               │
│          │ - Avatar                 │
└──────────┴──────────────────────────┘
```

---

## 9. Spacing Conventions

- **Section padding**: `py-20 px-6`
- **Card inner padding**: `p-5` or `p-6`
- **Max content width**: `max-w-5xl` (workspace), `max-w-4xl` (landing hero), `max-w-2xl` (forms)
- **Grid gaps**: `gap-4` (tight), `gap-6` (standard)
- **Border radius**: `rounded-xl` (12px) for cards, `rounded-lg` (8px) for inputs/buttons, `rounded-full` for pills

---

## 10. Don'ts (Anti-patterns)

1. ❌ **No dark mode colors** — no `bg-black`, `bg-[#0a0a0a]`, `text-white` on dark surfaces
2. ❌ **No cool grays** — no `#ccc`, `#ddd`, `#f5f5f5`. Use warm tones from the palette
3. ❌ **No Tailwind preset colors** — no `bg-blue-500`, `text-red-400`. Use semantic tokens
4. ❌ **No heavy borders** — borders should be subtle (`1px solid #e8e4df`), never thick or dark
5. ❌ **No excessive shadows** — shadows simulate paper stacking, not 3D depth
6. ❌ **No generic fonts** — always use the configured font stack (Inter, JetBrains Mono, Caveat)
7. ❌ **No glassmorphism/blur panels** — the ".glass-" prefix is historical; these are paper panels now
