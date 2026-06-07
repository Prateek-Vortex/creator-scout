# Creator Scout AI — UI Redesign & Brand Alignment Plan

We will overhaul the user interface of Creator Scout AI to make it feel premium, modern, and sassy, aligning with best-in-class SaaS platforms. 

We will transition the dashboard from a simple stacked page list to a multi-state workspace:
1. **Interactive Landing & Hero Page**: Introducing a bold, high-end landing page to capture the user's focus on first load.
2. **Sleek Tabbed Dashboard**: Organizing campaign actions into clean visual tabs (Brief, Strategy, Shortlist, Outreach, CRM, Export).
3. **Midnight Violet & Teal Glow Theme**: A beautiful dark-theme layout using CSS variables, blur filters (glassmorphism), and neon accent gradients.
4. **Interactive Micro-interactions**: Adding visual crawler progress logs, smooth hover states, and slide-in drawer animations.

---

## Proposed Changes

### [Component Name] Frontend Layout & Design System

#### [MODIFY] [globals.css](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/globals.css)
- Revise theme variables to introduce a dark-mode base color system:
  - Deep space base: `#090d16`
  - Card/Panel base: `rgba(17, 24, 39, 0.7)` (with blur)
  - Neon purple accent: `#a855f7`
  - Neon cyan/teal accent: `#06b6d4`
  - Custom animations (`fade-in-up`, `gradient-flow`).

#### [MODIFY] [page.tsx](file:///Users/prateeksaxena/Developer/projects/Ai%20content%20creator%20matching/apps/web/src/app/page.tsx)
- Restructure the UI into two core states:
  - **Landing State**: Sassy copywriting, prominent URL input box with a glowing purple outline, platform selector tags, and geo tags.
  - **Workspace State**: Side-navigation layout managing a tab-focused view:
    - **Tab 1: Brand Brief**: Extracted categories, values, and crawler evidence URLs in card grids.
    - **Tab 2: Creator Strategy**: Campaign filters, platforms, and find triggers.
    - **Tab 3: Shortlisted Matches**: Table view highlighting creator scores and why they fit.
    - **Tab 4: Outreach Composer**: Double-pane workspace showing selected creator info, compliance flags, and editable email pitch.
    - **Tab 5: CRM Kanban Board**: Multi-column board displaying pipeline cards (replied, accepted, content live).
    - **Tab 6: Export & Integrations**: CSV export interface.
- Add dynamic progress step animations when scanning a brand URL.

---

## Verification Plan

### Manual Verification
- Launch both servers and verify:
  1. Responsive layout of the new landing page.
  2. Tab switching without losing loaded campaign states.
  3. Interactive drawer opening on creator click.
  4. Glowing borders and micro-interactions on hover.
