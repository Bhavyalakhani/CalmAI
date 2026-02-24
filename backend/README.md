# CalmAI Backend

FastAPI backend for CalmAI - provides authentication, CRUD APIs, invite code patient onboarding, and LangChain RAG search for the therapist dashboard and patient journal.

## Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI app with lifespan, CORS, 8 routers
│   ├── config.py            # Settings (pydantic-settings) - env vars
│   ├── dependencies.py      # JWT auth dependency + role guard
│   ├── seed.py              # Seed script - creates therapist + 10 patients
│   ├── models/              # Pydantic request/response schemas
│   │   ├── user.py          # UserCreate, UserLogin, TokenResponse, TherapistResponse, PatientResponse, ProfileUpdate, NotificationPreferences, PasswordChange
│   │   ├── journal.py       # JournalCreate, JournalEntryResponse, JournalSubmitResponse
│   │   ├── conversation.py  # ConversationResponse, ConversationListResponse
│   │   ├── analytics.py     # TopicDistribution, TopicOverTime, RepresentativeEntry, EntryFrequency, DateRange, PatientAnalyticsResponse
│   │   ├── dashboard.py     # DashboardStats, TrendDataPoint
│   │   ├── invite.py        # InviteCodeResponse, InviteCodeCreate
│   │   ├── prompt.py        # PromptCreate, PromptResponse
│   │   └── rag.py           # RAGQuery, RAGResult, RAGResponse, ConversationMessage
│   ├── services/
│   │   ├── db.py            # Async MongoDB (Motor) - singleton Database class (9 collections)
│   │   ├── auth_service.py  # Password hashing (bcrypt), JWT encode/decode (python-jose)
│   │   └── rag_service.py   # LangChain RAG - embeddings, vector search, Gemini LLM, intent classification, fallback text search
│   └── routers/
│       ├── auth.py          # POST /auth/signup, POST /auth/login, GET /auth/me, POST /auth/refresh, PATCH /auth/profile, PATCH /auth/notifications, PATCH /auth/password, DELETE /auth/account
│       ├── patients.py      # GET /patients, GET /patients/{id}, POST /patients/invite, GET /patients/invites, DELETE /patients/{id}
│       ├── journals.py      # GET /journals, POST /journals, PATCH /journals/{id}, DELETE /journals/{id} (lazy-loads TopicModelInference)
│       ├── conversations.py # GET /conversations, GET /conversations/topics, GET /conversations/severities
│       ├── analytics.py     # GET /analytics/{patient_id}
│       ├── dashboard.py     # GET /dashboard/stats, GET /dashboard/mood-trend/{patient_id} (NaN-safe mood aggregation)
│       ├── search.py        # POST /search/rag (therapist-only, LangChain RAG with intent routing)
│       └── prompts.py       # POST /prompts, GET /prompts/{patient_id}, GET /prompts/{patient_id}/all, PATCH /prompts/{prompt_id}/respond
├── tests/
│   ├── conftest.py          # MockDatabase, AsyncCursorMock, fixtures (mock_db, therapist_client, patient_client)
│   ├── test_app.py          # 3 tests (startup, health check)
│   ├── test_auth.py         # 42 tests (login, signup, me, refresh, invite code, profile, notifications, password, delete account)
│   ├── test_auth_service.py # 12 tests (hash, verify, JWT encode/decode)
│   ├── test_patients.py     # 22 tests (list, get, invite generation, invite listing, remove patient)
│   ├── test_journals.py     # 16 tests (list, create, edit, delete, analytics refresh)
│   ├── test_conversations.py# 13 tests (paginated, topic/severity filters)
│   ├── test_analytics.py    # 21 tests (topic distribution, topics over time, representative entries, model version)
│   ├── test_dashboard.py    # 8 tests (stats, mood trend, NaN handling)
│   ├── test_search.py       # 26 tests (RAG, conversation history, topic detection)
│   └── test_prompts.py      # 15 tests (create prompt, list pending, list all, respond)
├── requirements.txt
└── pytest.ini
```

## API Endpoints (29)

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | - | Create account (therapist or patient, patients require invite code) |
| POST | `/auth/login` | - | Login, returns JWT access + refresh tokens |
| GET | `/auth/me` | Bearer | Get current user profile |
| POST | `/auth/refresh` | - | Refresh access token |
| PATCH | `/auth/profile` | Bearer | Update user profile fields (name, specialization, etc.) |
| PATCH | `/auth/notifications` | Bearer | Update notification preferences |
| PATCH | `/auth/password` | Bearer | Change password (requires current password) |
| DELETE | `/auth/account` | Bearer | Delete user account (requires password confirmation) |

### Patients

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/patients` | Therapist | List therapist's patients |
| GET | `/patients/{id}` | Therapist | Get single patient |
| POST | `/patients/invite` | Therapist | Generate single-use invite code (8-char, 7-day expiry) |
| GET | `/patients/invites` | Therapist | List all invite codes (with used/active status) |
| DELETE | `/patients/{id}` | Therapist | Remove patient from therapist's roster |

### Journals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/journals` | Bearer | List journals (patients see own, therapists see their patients') |
| POST | `/journals` | Patient | Submit new journal entry → `incoming_journals` staging collection |
| PATCH | `/journals/{id}` | Patient | Edit an existing journal entry (content, mood) |
| DELETE | `/journals/{id}` | Patient | Delete a journal entry |

### Conversations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/conversations` | Therapist | Paginated conversation list (topic, severity, search filters) |
| GET | `/conversations/topics` | Therapist | List distinct conversation topics for filter UI |
| GET | `/conversations/severities` | Therapist | List distinct severity levels for filter UI |

### Analytics & Dashboard

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics/{patient_id}` | Bearer | Patient analytics (topicDistribution, topicsOverTime, representativeEntries, modelVersion, frequency, etc.) |
| GET | `/dashboard/stats` | Therapist | Aggregate counts (patients, journals, conversations, active) |
| GET | `/dashboard/mood-trend/{id}` | Bearer | Mood data points over last N days (NaN-safe aggregation) |

### RAG Search

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/search/rag` | Therapist | RAG search with intent routing — vector search + Gemini answer generation |

### Prompts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/prompts` | Therapist | Create a reflection prompt for a patient |
| GET | `/prompts/{patient_id}` | Bearer | Get pending prompts for a patient |
| GET | `/prompts/{patient_id}/all` | Therapist | Get all prompts (pending + responded) for a patient |
| PATCH | `/prompts/{prompt_id}/respond` | Bearer | Submit a response to a prompt |

### Other

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | - | Health check |

## Setup

```bash
cd backend
pip install -r requirements.txt

# configure (root .env is used by the backend)
cp ../.env.example ../.env
# fill in: MONGODB_URI, JWT_SECRET, GEMINI_API_KEY, SEED_PASSWORD
```

## Running

```bash
# seed database with therapist + patients
cd backend
python -m app.seed

# start server
uvicorn app.main:app --reload --port 8000

# run tests
pytest tests/ -v
pytest tests/ -v --cov --cov-report=term-missing
```

## RAG Pipeline

The RAG service (`app/services/rag_service.py`) implements intent-based routing with LangChain LCEL chains. See the [RAG Intent Routing](#rag-intent-routing) section below for details.

The vector search index (`vector_index`) is created automatically by `python src/storage/mongodb_client.py create-indexes` in the data-pipeline. Supports filtering by `patient_id` and `source_type` (journal/conversation).

## Authentication

- JWT access tokens (60 min expiry) + refresh tokens (7 day expiry)
- Password hashing via `passlib` + `bcrypt`
- Role-based access: `require_role("therapist")` / `require_role("patient")`
- Token format: `{ "sub": user_id, "role": "therapist"|"patient", "type": "access"|"refresh" }`

## Invite Code System

Therapists generate invite codes that patients use during signup to link accounts.

1. Therapist calls `POST /patients/invite` - generates 8-char uppercase alphanumeric code (via `secrets` module)
2. Code stored in `invite_codes` collection with 7-day expiry, `is_used=False`
3. Patient signs up with the code in the `therapistId` field
4. Backend validates: code exists (404) -> not used (410) -> not expired (410)
5. On success: patient created, linked to therapist via `$addToSet` on `patient_ids`, code marked `is_used=True`

Code config: `INVITE_CODE_LENGTH = 8`, `INVITE_CODE_EXPIRY_DAYS = 7`, max 10 collision retries.

## Journal Submission Flow

1. Patient submits via `POST /journals` with content + optional mood
2. Backend writes to `incoming_journals` collection with `is_processed=False`
3. Airflow DAG 2 (every 12 hours) picks up unprocessed entries
4. DAG 2 preprocesses, validates, embeds, stores to `rag_vectors` + `journals`
5. DAG 2 updates `patient_analytics` and marks entries as processed

## Topic Classification (BERTopic)

The journals router (`routers/journals.py`) lazy-loads `TopicModelInference(model_type="journals")` from the data-pipeline's `src/topic_modeling/` module. When a patient fetches journals, each entry is classified with BERTopic-discovered topics. If the model is unavailable (not trained yet or import error), entries are returned as "unclassified".

## Patient Analytics Schema

The `patient_analytics` MongoDB collection (populated by Airflow DAG 2) stores per-patient analytics documents:

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | string (unique) | Patient identifier |
| `total_entries` | int | Total journal entries |
| `topic_distribution` | list | `{topicId, label, keywords, percentage, count}` per topic |
| `topics_over_time` | list | `{period, topicId, label, count}` per time period |
| `representative_entries` | list | `{topicId, label, journalId, content, similarity}` per topic |
| `avg_word_count` | float | Average words per entry |
| `entry_frequency` | dict | Counts by month (`YYYY-MM` keys) |
| `date_range` | dict | `{first, last, span_days}` |
| `model_version` | string | BERTopic model version or `"unavailable"` |
| `computed_at` | datetime | When analytics were computed |

The `GET /analytics/{patient_id}` endpoint returns these fields as `topicDistribution`, `topicsOverTime`, `representativeEntries`, and `modelVersion` (camelCase).

## Prompts System

Therapists assign reflection prompts to patients. Patients see pending prompts on their journal page and can respond with a journal entry.

1. Therapist calls `POST /prompts` with `patientId` + `promptText`
2. Prompt stored in `prompts` collection with `status: "pending"`
3. Patient views pending prompts via `GET /prompts/{patient_id}`
4. Patient responds via `PATCH /prompts/{prompt_id}/respond` — updates status to `"responded"` and links the journal

Models: `PromptCreate` (patientId, promptText) and `PromptResponse` (promptId, therapistId, therapistName, patientId, promptText, createdAt, status, responseJournalId, responseContent, respondedAt).

## RAG Intent Routing

The RAG service (`app/services/rag_service.py`) uses intent classification to route queries:

1. **Intent Classification**: `classify_intent()` determines if a query is patient-specific, general clinical, or conversational
2. **Router Chain**: `get_router_chain()` and `get_general_chain()` provide specialized LCEL pipelines per intent
3. **Vector Search**: MongoDB Atlas `$vectorSearch` on `rag_vectors.embedding` (cosine similarity)
4. **LLM Generation**: Gemini (`gemini-2.5-flash`) via `langchain-google-genai`
5. **Fallback**: Text-based `$regex` search when vector search returns no results

## NaN-Safe Mood Handling

The `GET /journals` and `GET /dashboard/mood-trend/{id}` endpoints sanitize mood values from MongoDB. Entries with `NaN` mood (from pipeline-processed entries without mood data) are converted to `None` before Pydantic validation to prevent `finite_number` validation errors.

## MongoDB Collections (9)

| Collection | Purpose |
|---|---|
| `users` | Auth + profiles (therapists and patients) |
| `rag_vectors` | Unified vector store for RAG retrieval |
| `conversations` | Raw + processed conversation data |
| `journals` | Raw + processed journal data |
| `incoming_journals` | Staging area for new journal entries |
| `patient_analytics` | Per-patient BERTopic analytics |
| `pipeline_metadata` | Pipeline execution audit trail |
| `invite_codes` | Patient onboarding invite codes |
| `prompts` | Therapist-assigned reflection prompts |

## Testing

178 tests across 11 test files. All external services (MongoDB, Gemini, embedding model) are mocked.

```bash
pytest tests/ -v            # 178 tests
pytest tests/ -v --cov      # with coverage
```
