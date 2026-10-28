# Phase 5 — Frontend Foundation + Design System

## Goal
Set up the React app with a clean, premium B2B design system and a typed API layer. Build no feature widgets yet.

## Structure
```
frontend/src/
  components/ui/          # Card, Badge, Button, Select, DateInput, Tooltip, Skeleton, EmptyState, ErrorState, Table
  components/layout/      # AppShell, Header, Section
  services/api.ts         # fetch wrapper, base URL from VITE_API_BASE_URL
  hooks/                  # useApi / useAnalysis (loading, error, retry, abort)
  types/api.ts            # mirrors backend Pydantic schemas
  lib/format.ts           # number, MW, %, and date formatting (Europe/London + UTC)
  pages/Dashboard.tsx
  App.tsx  main.tsx
```

## Design system (clean, restrained, presentation-ready)
**Colour tokens** (Tailwind theme extension):
| Token | Use | Value |
|---|---|---|
| `bg` | Page background | `#F7F8FA` |
| `surface` | Cards | `#FFFFFF` |
| `border` | Hairlines | `#E5E7EB` |
| `ink` / `ink-muted` | Text | `#0F172A` / `#64748B` |
| `forecast` | Forecast series, primary accent | `#2563EB` (blue) |
| `actual` | Actual series | `#059669` (green) |
| `over` / `under` | Positive / negative error | `#D97706` / `#7C3AED` |
| `danger` / `warn` / `ok` | Status | `#DC2626` / `#F59E0B` / `#16A34A` |

**Typography:** Inter (or the system UI font). Use tabular numbers (`font-variant-numeric: tabular-nums`) for every figure.
- Page title 20/28 semibold · section title 14/20 semibold uppercase tracking-wide muted · KPI value 28/32 semibold · body 14/20 · caption 12/16

**Layout:**
- Max width 1440px with a 24px gutter (16px on tablet). 12-column grid, 16px gap.
- Cards: 1px border, 12px radius, subtle shadow (`shadow-sm`), 20px padding.
- Responsive breakpoints: desktop ≥1280, laptop ≥1024, tablet ≥768. No horizontal page scroll.

**Principles:** no heavy gradients or decorative animation. Use one accent per meaning. Every number gets a unit. Every timestamp gets a timezone label (`GMT`/`BST` or `UTC`).

**States:** every data component supports `loading` (a skeleton matching the final layout), `error` (message + Retry button), and `empty` (an explanation + next action).

**Accessibility:** labelled controls, visible focus rings, sufficient contrast, and chart colours that differ by more than hue alone (e.g. a dashed forecast line).

## Header (wired to `/api/meta`)
- Product: **Wind Forecast Intelligence**
- Subtitle: **UK National Wind Generation**
- Selected analysis period
- Source badge: `Elexon BMRS` and `LIVE` (green) or `DEMO FIXTURE` (amber)
- "Last successful fetch: 12 Jan 2026, 09:14 GMT"

## Exit check
- [ ] `npm run build` and `npm run lint` pass, and TypeScript runs in strict mode
- [ ] The app shell renders a header with **real** `/api/meta` data
- [ ] Stopping the backend shows the error state with a working Retry button

Stop and report.
