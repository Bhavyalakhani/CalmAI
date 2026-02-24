# CalmAI Frontend

Next.js 16 therapist dashboard and patient journaling UI for CalmAI. Dark zinc theme, 14 routes, 199 Vitest tests.

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.1.6 | App Router, server/client components |
| React | 19.2.3 | UI rendering (React Compiler enabled via `babel-plugin-react-compiler`) |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 4 | Utility-first styling (`tw-animate-css` for animations) |
| shadcn/ui | — | 22 UI components (accordion, avatar, badge, button, card, chart, dialog, dropdown-menu, input, label, progress, scroll-area, select, separator, sheet, sidebar, skeleton, switch, tabs, textarea, theme-toggle, tooltip) |
| Recharts | 2.15 | Charts (bar, sparkline, area) |
| Lucide Icons | 0.575 | Icon library |
| react-markdown | 10.1 | Markdown rendering in RAG chat |
| Vitest | 4.0.18 | Test runner |
| React Testing Library | 16.3.2 | Component testing |
| @testing-library/user-event | 14.6 | User interaction simulation |

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Routes (14)

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
| `/dashboard/settings` | Interactive profile editing, notification toggles, password change, guarded delete-account flow |

### Patient Journal

| Route | Description |
|---|---|
| `/journal` | Entry composer with mood selector (1–5), word count, timeline with topic badges |
| `/journal/insights` | Patient's own BERTopic analytics — topic distribution bars, monthly frequency chart, summary stats |
| `/journal/prompts` | Therapist prompt cards with pending/answered states |
| `/journal/settings` | Patient profile, linked therapist, privacy notice |

## Architecture

- **Dark zinc theme** via `class="dark"` on html element, dark/light mode toggle with `ThemeProvider` (localStorage persistence)
- **Collapsible sidebar** for therapist dashboard, top nav for patient journal
- **Mobile responsive** via `useIsMobile()` hook (768px breakpoint) in `src/hooks/use-mobile.ts`
- **API client** (`src/lib/api.ts`) — 31 typed fetch wrappers for all backend endpoints
- **Auth context** (`src/lib/auth-context.tsx`) — login/signup/logout, JWT token management, role-based redirect, route guards (therapists blocked from `/journal/*`, patients blocked from `/dashboard/*`)
- **Theme context** (`src/lib/theme-context.tsx`) — `ThemeProvider` + `useTheme()` hook with dark/light/system modes and localStorage persistence
- **Domain types** (`src/types/index.ts`) — TypeScript types matching backend models

### API Client Functions

| Category | Functions |
|---|---|
| Auth | `login`, `signup`, `getMe`, `logout` |
| Profile | `updateProfile`, `updateNotifications`, `changePassword`, `deleteAccount` |
| Patients | `fetchPatients`, `fetchPatient`, `removePatient` |
| Invite Codes | `generateInviteCode`, `fetchInviteCodes` |
| Journals | `fetchJournals`, `submitJournal`, `editJournal`, `deleteJournal` |
| Conversations | `fetchConversations`, `fetchConversationTopics`, `fetchConversationSeverities` |
| Analytics | `fetchAnalytics` |
| Dashboard | `fetchDashboardStats`, `fetchMoodTrend` |
| RAG Search | `ragSearch` |
| Prompts | `fetchPrompts`, `fetchAllPrompts`, `createPrompt` |
| Token helpers | `getAccessToken`, `getRefreshToken`, `setTokens`, `clearTokens` |

### Domain Types

| Type | Purpose |
|---|---|
| `UserRole`, `User`, `Therapist`, `Patient` | Auth and user profiles |
| `MoodScore`, `JournalEntry` | Journal entries with mood (1–5) |
| `SeverityLevel`, `Conversation` | Conversations with severity classification |
| `TopicCount`, `SeverityCount` | Aggregation types for filter dropdowns |
| `TopicDistribution`, `TopicOverTime`, `RepresentativeEntry` | BERTopic analytics per patient |
| `EntryFrequency`, `DateRange`, `PatientAnalytics` | Patient analytics metadata |
| `DashboardStats`, `TrendDataPoint` | Therapist dashboard aggregate data |
| `ConversationMessage`, `RAGQuery`, `RAGResult`, `RAGResponse` | RAG chat types |
| `PromptStatus`, `TherapistPrompt` | Therapist prompt system |

## Testing

199 tests across 18 files (16 page/layout tests + 2 lib tests).

```bash
npm test               # run all tests
npm run test:watch     # watch mode
npm run test:coverage  # with coverage
```

All backend calls are mocked via `vi.mock()` on `@/lib/api` and `@/lib/auth-context`. Navigation mocked via `next/navigation`. Shared mock data in `src/__tests__/mock-api-data.ts`.

### Test Files

| File | Tests | Covers |
|---|---|---|
| `page.test.tsx` (landing) | 15 | Hero section, feature cards, stats, navigation |
| `login/page.test.tsx` | 9 | Login form, validation, redirect on success |
| `signup/page.test.tsx` | 15 | Role selection, form validation, invite code, signup flow |
| `dashboard/page.test.tsx` | 6 | Overview stats, patient list, analytics panel |
| `dashboard/layout.test.tsx` | 5 | Sidebar navigation, auth guard |
| `dashboard/patients/page.test.tsx` | 10 | Patient grid, search, invite code dialog |
| `dashboard/patients/[id]/page.test.tsx` | 12 | Patient profile, journal timeline, analytics sidebar |
| `dashboard/conversations/page.test.tsx` | 6 | Conversation explorer, filters |
| `dashboard/analytics/page.test.tsx` | 14 | Bias reports, distribution charts |
| `dashboard/search/page.test.tsx` | 9 | RAG chat, conversation history, sources |
| `dashboard/settings/page.test.tsx` | 18 | Profile editing, notifications, password change, account deletion |
| `journal/page.test.tsx` | 18 | Entry composer, mood selector, timeline |
| `journal/layout.test.tsx` | 5 | Top nav, auth guard |
| `journal/insights/page.test.tsx` | 12 | Topic distribution, frequency charts |
| `journal/prompts/page.test.tsx` | 9 | Prompt cards, pending/answered states |
| `journal/settings/page.test.tsx` | 10 | Patient profile, linked therapist |
| `lib/utils.test.ts` | 5 | `cn()` merge utility |
| `lib/mock-data.test.ts` | 20 | Mock data shape + helper tests (legacy) |

## Build

```bash
npm run build    # production build (all 14 routes)
npm run lint     # eslint
```
