# CalmAI Frontend

Next.js 16 therapist dashboard and patient journaling UI for CalmAI. Dark zinc theme, 15 routes, 175 Vitest tests.

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.1.6 | App Router, server/client components |
| React | 19.2.3 | UI rendering |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 4 | Utility-first styling |
| shadcn/ui | — | 20+ UI components (button, card, dialog, select, sidebar, etc.) |
| Recharts | — | Charts (bar, sparkline, area) |
| Lucide Icons | — | Icon library |
| react-markdown | — | Markdown rendering in RAG chat |
| Vitest | 4.0.18 | Test runner |
| React Testing Library | 16.3.2 | Component testing |

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Routes (15)

### Marketing

| Route | Description |
|---|---|
| `/` | Landing page — hero glow, feature cards, workflow section, pricing, stats |
| `/login` | Login form with role-aware redirect |
| `/signup` | 2-step signup with role selection (therapist/patient, invite code required for patients) |

### Therapist Dashboard

| Route | Description |
|---|---|
| `/dashboard` | Overview — stat cards, patient list, per-patient BERTopic analytics, mood trends, RAG assistant panel |
| `/dashboard/patients` | Patient grid with search, analytics badges, invite code dialog for onboarding |
| `/dashboard/patients/[id]` | Patient profile — journal timeline (search/filter/sort/pagination), BERTopic topic distribution sidebar, monthly frequency, mood trend |
| `/dashboard/conversations` | Conversation explorer — keyword search, topic/severity dropdown filters, removable filter chips, paginated cards |
| `/dashboard/analytics` | Bias & distribution reports — BERTopic topics, severity, temporal patterns, patient distributions (powered by backend analytics APIs) |
| `/dashboard/search` | RAG chat assistant — conversation history, markdown rendering, split source display (journals + conversations), turn limit (10), patient context selector |
| `/dashboard/settings` | Interactive profile editing, notification toggles, guarded delete-account flow |

### Patient Journal

| Route | Description |
|---|---|
| `/journal` | Entry composer with mood selector (1–5), word count, timeline with topic badges |
| `/journal/insights` | Patient's own BERTopic analytics — topic distribution bars, monthly frequency chart, summary stats |
| `/journal/prompts` | Therapist prompt cards with pending/answered states |
| `/journal/settings` | Patient profile, linked therapist, privacy notice |

## Architecture

- **Dark zinc theme** via `class="dark"` on html element, shadcn/ui components
- **Collapsible sidebar** for therapist dashboard, top nav for patient journal
- **API client** (`src/lib/api.ts`) — typed fetch wrappers for all backend endpoints (auth, patients, journals, conversations, analytics, dashboard, RAG search, invite codes)
- **Auth context** (`src/lib/auth-context.tsx`) — login/signup/logout, JWT token management, role-based redirect
- **Domain types** (`src/types/index.ts`) — TypeScript types matching backend models, including `SeverityLevel` (`crisis` | `severe` | `moderate` | `mild` | `unknown`), `TopicDistribution`, `TopicOverTime`, `RepresentativeEntry`

## Testing

175 tests across 18 files (16 page/layout tests + 2 lib tests).

```bash
npm test               # run all tests
npm run test:watch     # watch mode
npm run test:coverage  # with coverage
```

All backend calls are mocked via `vi.mock()` on `@/lib/api` and `@/lib/auth-context`. Navigation mocked via `next/navigation`. Shared mock data in `src/__tests__/mock-api-data.ts`.

## Build

```bash
npm run build    # production build (all 15 routes)
npm run lint     # eslint
```
