# CalmAI Backend

FastAPI backend for CalmAI - provides authentication, CRUD APIs, invite code patient onboarding, and LangChain RAG search for the therapist dashboard and patient journal.

## Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI app with lifespan, CORS, 7 routers
│   ├── config.py            # Settings (pydantic-settings) - env vars
│   ├── dependencies.py      # JWT auth dependency + role guard
│   ├── seed.py              # Seed script - creates therapist + 10 patients
│   ├── models/              # Pydantic request/response schemas
│   │   ├── user.py          # UserCreate, UserLogin, TokenResponse, TherapistResponse, PatientResponse
│   │   ├── journal.py       # JournalCreate, JournalEntryResponse, JournalSubmitResponse
│   │   ├── conversation.py  # ConversationResponse, ConversationListResponse
│   │   ├── analytics.py     # ThemeDistribution, EntryFrequency, DateRange, PatientAnalyticsResponse
│   │   ├── dashboard.py     # DashboardStats, TrendDataPoint
│   │   ├── invite.py        # InviteCodeResponse, InviteCodeCreate
│   │   └── rag.py           # RAGQuery, RAGResult, RAGResponse, ConversationMessage
│   ├── services/
│   │   ├── db.py            # Async MongoDB (Motor) - singleton Database class
│   │   ├── auth_service.py  # Password hashing (bcrypt), JWT encode/decode (python-jose)
│   │   └── rag_service.py   # LangChain RAG - embeddings, vector search, Gemini LLM, fallback text search on empty results
│   └── routers/
│       ├── auth.py          # POST /auth/signup (invite code validation), POST /auth/login, GET /auth/me, POST /auth/refresh
│       ├── patients.py      # GET /patients, GET /patients/{id}, POST /patients/invite, GET /patients/invites (therapist-only)
│       ├── journals.py      # GET /journals, POST /journals (writes to incoming_journals)
│       ├── conversations.py # GET /conversations (paginated, filterable, therapist-only)
│       ├── analytics.py     # GET /analytics/{patient_id}
│       ├── dashboard.py     # GET /dashboard/stats, GET /dashboard/mood-trend/{patient_id} (therapist-only)
│       └── search.py        # POST /search/rag (therapist-only, LangChain RAG)
├── tests/
│   ├── conftest.py          # MockDatabase, AsyncCursorMock, fixtures (mock_db, therapist_client, patient_client)
│   ├── test_app.py          # 3 tests (startup, health check)
│   ├── test_auth.py         # 18 tests (login, signup, me, refresh, invite code validation)
│   ├── test_auth_service.py # 12 tests (hash, verify, JWT encode/decode)
│   ├── test_patients.py     # 16 tests (list, get, invite generation, invite listing)
│   ├── test_journals.py     # 11 tests
│   ├── test_conversations.py# 7 tests
│   ├── test_analytics.py    # 8 tests
│   ├── test_dashboard.py    # 7 tests
│   └── test_search.py       # 23 tests (RAG, conversation history, theme detection)
├── requirements.txt
└── pytest.ini
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | - | Health check |
| POST | `/auth/signup` | - | Create account (therapist or patient, patients require invite code) |
| POST | `/auth/login` | - | Login, returns JWT tokens |
| GET | `/auth/me` | Bearer | Get current user profile |
| POST | `/auth/refresh` | - | Refresh access token |
| POST | `/patients/invite` | Therapist | Generate single-use invite code (8-char, 7-day expiry) |
| GET | `/patients/invites` | Therapist | List all invite codes (with used/active status) |
| GET | `/patients` | Therapist | List therapist's patients |
| GET | `/patients/{id}` | Therapist | Get single patient |
| GET | `/journals` | Bearer | List journals (patients see own, therapists see their patients') |
| POST | `/journals` | Patient | Submit new journal entry → `incoming_journals` staging collection |
| GET | `/conversations` | Therapist | Paginated conversation list (topic, severity, search filters) |
| GET | `/analytics/{patient_id}` | Bearer | Patient analytics (theme distribution, frequency, etc.) |
| GET | `/dashboard/stats` | Therapist | Aggregate counts (patients, journals, conversations, active) |
| GET | `/dashboard/mood-trend/{id}` | Therapist | Mood data points over last N days |
| POST | `/search/rag` | Therapist | RAG search - vector search + Gemini answer generation |

## Setup

```bash
cd backend
pip install -r requirements.txt

# configure (root .env is used by the backend)
cp ../.env.example ../.env
# fill in: MONGODB_URI, JWT_SECRET, GEMINI_API_KEY
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

The RAG service (`app/services/rag_service.py`) implements:

1. **Embedding**: `sentence-transformers/all-MiniLM-L6-v2` (384 dims) via `langchain-huggingface`
2. **Vector Search**: MongoDB Atlas `$vectorSearch` on `rag_vectors.embedding` (cosine similarity)
3. **LLM Generation**: Gemini (`gemini-2.5-flash`) via `langchain-google-genai`
4. **LCEL Chain**: prompt template → Gemini → string output parser
5. **Fallback**: Text-based `$regex` search when vector search returns no results or encounters errors

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
3. Airflow DAG 2 (every 30 min) picks up unprocessed entries
4. DAG 2 preprocesses, validates, embeds, stores to `rag_vectors` + `journals`
5. DAG 2 updates `patient_analytics` and marks entries as processed

## Testing

108 tests across 10 test files. All external services (MongoDB, Gemini, embedding model) are mocked.

```bash
pytest tests/ -v            # 108 tests
pytest tests/ -v --cov      # with coverage
```
