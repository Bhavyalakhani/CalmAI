# CalmAI

A B2B SaaS platform for licensed therapists - helps mental health professionals organize, retrieve, and reason over patient journal data using RAG and semantic search. All clinical judgment stays with humans.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Components](#components)
- [Tech Stack](#tech-stack)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Contributing](#contributing)

## Overview

CalmAI consists of two main modules:

1. **Patient Journaling Module** - Patients write journal entries, receive BERTopic-powered analytical insights, and respond to therapist-assigned prompts
2. **Therapist Dashboard** - Timeline view, BERTopic topic modeling, per-patient analytics, trend analysis, and a RAG assistant for natural language queries over patient data

The platform **never makes diagnoses or treatment recommendations** - it surfaces information so therapists can make better-informed clinical decisions.

### Recent Frontend Updates

- `Conversation Explorer` now supports keyword search plus dynamic topic and severity dropdown filters with removable filter chips.
- `Analytics & Bias Reports` now reads conversation topic/severity distributions from backend endpoints instead of static placeholder values.
- `Settings` now includes interactive profile editing, notification toggles, and guarded account deletion confirmation.
- The landing page now includes hero glow treatment, an informational workflow section, and pricing cards.

### Analytics Flow

Each patient gets unique analytics computed by BERTopic with Gemini LLM-generated topic labels:

```
Patient writes journal entry
        │
        ▼
Backend writes to incoming_journals (staging)
        │
        ▼
Airflow DAG 2 (every 30 min)
├── Preprocess & validate entry
├── Generate embeddings (384-dim)
├── Store in rag_vectors + journals
├── Recompute patient analytics via BERTopic
│   ├── Topic distribution (% per topic)
│   ├── Topics over time (monthly trends)
│   ├── Representative entries (most typical per topic)
│   ├── Entry frequency (monthly counts)
│   └── Date range & word count stats
└── Upsert to patient_analytics collection
        │
        ▼
Analytics displayed on:
├── Therapist Dashboard Overview (/dashboard)      — per-patient analytics panel
├── Patient Profile (/dashboard/patients/[id])     — topic distribution, stats, monthly frequency
├── Patient Insights (/journal/insights)           — patient's own analytics view
└── Analytics Page (/dashboard/analytics)          — bias reports across all patients
```

## System Architecture

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────────┐
│   Frontend   │────►│   Backend    │────►│    MongoDB Atlas       │
│  (React/Next)│◄────│  (FastAPI)   │◄────│  (Vector Store + Raw) │
└──────────────┘     └──────┬───────┘     └───────────┬───────────┘
                            │                         │
                     ┌──────▼───────┐          ┌──────▼──────┐
                     │   BERTopic   │          │    Data     │
                     │  + MLflow    │          │  Pipeline   │
                     │  + Gemini    │          │  (Airflow)  │
                     └──────────────┘          └─────────────┘
```

## Project Structure

```
CalmAI/
├── .github/
│   ├── copilot-instructions.md     # Copilot context and conventions
│   └── workflows/
│       └── ci.yml                  # CI pipeline (data-pipeline + backend + frontend + Docker)
│
├── data-pipeline/          # Data acquisition, processing, and storage
│   ├── dags/               #   2 Airflow DAGs (batch + incoming journals)
│   ├── src/                #   Pipeline source code (10 modules)
│   │   ├── acquisition/    #     Data download + Gemini journal generation
│   │   ├── preprocessing/  #     Domain-specific text cleaning
│   │   ├── validation/     #     Schema validation with pipeline gate
│   │   ├── bias_detection/ #     BERTopic-based bias analysis
│   │   ├── embedding/      #     Sentence-transformer embedding generation
│   │   ├── storage/        #     MongoDB client (CRUD, indexes, batch inserts)
│   │   ├── analytics/      #     Per-patient analytics computation
│   │   ├── topic_modeling/  #    BERTopic training, inference, validation, MLflow tracking
│   │   └── alerts/         #     Email notifications for DAG completion
│   ├── tests/              #   322 pytest tests across 15 files
│   ├── models/             #   BERTopic model artifacts (safetensors)
│   ├── mlruns/             #   MLflow experiment tracking (local)
│   ├── configs/            #   Configuration and patient profiles
│   ├── data/               #   Raw, processed, and embedded data
│   ├── reports/            #   Bias and schema validation reports
│   ├── docker-compose.yaml #   Full Airflow cluster (6 containers)
│   ├── Dockerfile          #   Custom Airflow image
│   └── run_pipeline.py     #   Local runner (no Airflow)
│
├── frontend/               # Web application
│   ├── src/
│   │   ├── app/            #   Next.js App Router (15 routes)
│   │   │   ├── page.tsx            # Landing page
│   │   │   ├── login/              # Login page
│   │   │   ├── signup/             # 2-step signup (role selection → form, invite code for patients)
│   │   │   ├── dashboard/          # Therapist dashboard (7 sub-routes)
│   │   │   │   ├── page.tsx        #   Overview - stats, patient list, analytics, RAG panel
│   │   │   │   ├── patients/       #   Patient grid with search + invite code dialog
│   │   │   │   ├── patients/[id]/  #   Patient profile - journal timeline, BERTopic analytics
│   │   │   │   ├── conversations/  #   Conversation explorer with topic/severity
│   │   │   │   ├── analytics/      #   Bias reports & distribution charts
│   │   │   │   ├── search/         #   RAG chat assistant with conversation history + markdown
│   │   │   │   └── settings/       #   Profile & pipeline status
│   │   │   └── journal/            # Patient journal (4 sub-routes)
│   │   │       ├── page.tsx        #   Entry composer, mood selector, timeline
│   │   │       ├── insights/       #   BERTopic analytics - topic distribution, frequency charts
│   │   │       ├── prompts/        #   Therapist prompts & responses
│   │   │       └── settings/       #   Patient profile & privacy
│   │   ├── components/ui/  #   shadcn/ui components (20+)
│   │   ├── lib/            #   API client, auth context, utilities
│   │   └── types/          #   TypeScript domain types
│   ├── vitest.config.ts    #   Vitest configuration (jsdom, React)
│   └── package.json
│
├── backend/                # API server
│   ├── app/                #   FastAPI app (main, config, dependencies, seed)
│   │   ├── models/         #   Pydantic schemas (user, journal, conversation, analytics, dashboard, invite, rag)
│   │   ├── routers/        #   7 routers: auth, patients, journals, conversations, analytics, dashboard, search
│   │   └── services/       #   db (Motor), auth_service (JWT/bcrypt), rag_service (LangChain)
│   └── tests/              #   111 pytest tests across 10 files
│
├── dvc.yaml                # DVC pipeline stages (wdir: data-pipeline)
├── .dvc/config             # DVC remote storage config (GCS)
├── docs/                   # Project documentation
├── assets/                 # Static assets
└── logs/                   # Application logs
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Docker Desktop (with WSL 2 on Windows)
- MongoDB Atlas account
- Google Gemini API key

### Run the Data Pipeline

```bash
# Clone
git clone https://github.com/your-org/CalmAI.git
cd CalmAI

# Virtual environment
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r data-pipeline/requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys and MongoDB URI
cp .env.example data-pipeline/.env
# Edit data-pipeline/.env (adds Airflow, Postgres, SMTP settings for Docker)

# Option A: Run locally
python run_pipeline.py

# Option B: Run with Airflow (Docker)
docker compose build
docker compose up airflow-init
docker compose up -d
# Open http://localhost:8080 → trigger calm_ai_data_pipeline
```

For detailed setup instructions, see the [data-pipeline README](data-pipeline/README.md).

### Pull Existing Data (DVC)

If artifacts have already been pushed to GCS by a team member:

```bash
cd data-pipeline
dvc pull
```

### Run the Backend

```bash
cd backend
pip install -r requirements.txt

# configure (root .env must exist with MONGODB_URI, JWT_SECRET, GEMINI_API_KEY, SEED_PASSWORD)
python -m app.seed                # Seed therapist (dr.chen@calmai.com) + 10 patients
uvicorn app.main:app --reload     # Start server at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Run the Frontend

```bash
cd frontend
npm install
npm run dev                   # Start dev server at http://localhost:3000
npm run build                 # Production build
```

### MLflow UI

```bash
cd data-pipeline
mlflow ui                     # Open http://localhost:5000
```

## Components

### Data Pipeline

The data pipeline handles the complete data lifecycle including model training:

| Stage | Description |
|---|---|
| **Acquisition** | Downloads 2 HuggingFace datasets + generates 1,000 synthetic journals via Gemini API |
| **Preprocessing** | Domain-specific text cleaning that preserves clinical language markers |
| **Validation** | Expectation-based schema validation with a pipeline gate (halts on failure) |
| **Embedding** | 384-dim vectors from `sentence-transformers/all-MiniLM-L6-v2` |
| **Topic Modeling** | Three independent BERTopic models (journals, conversations, severity) with Gemini LLM labeling |
| **Bias Detection** | BERTopic-based topic/severity analysis with visualizations and underrepresentation flagging |
| **Patient Analytics** | Per-patient topic distribution, frequency, trends, representative entries |
| **Storage** | MongoDB Atlas with unified `rag_vectors` collection for vector search |
| **Orchestration** | 2 Airflow DAGs — batch pipeline (23 tasks) + incoming journal micro-batch (10 tasks, every 30 min) |
| **Experiment Tracking** | MLflow local file-backed — logs hyperparameters, metrics, model artifacts per training run |
| **Versioning** | DVC with GCS remote for full artifact reproducibility |

See [data-pipeline/README.md](data-pipeline/README.md) for comprehensive documentation.

### Topic Modeling (BERTopic + MLflow)

Three independent BERTopic models for unsupervised topic discovery and severity classification:

| Feature | Detail |
|---|---|
| **Models** | `bertopic_journals`, `bertopic_conversations`, and `bertopic_severity` — unsupervised topic/severity discovery |
| **Severity** | The severity model clusters conversations by emotional intensity; Gemini LLM labels clusters as `crisis`, `severe`, `moderate`, or `mild` |
| **Labels** | Gemini LLM generates clinically descriptive topic labels (e.g. "Anxiety and daily worry") |
| **Representations** | Multi-aspect: KeyBERTInspired + Gemini LLM + MaximalMarginalRelevance |
| **Tuning** | Grid search over UMAP/HDBSCAN hyperparameters with composite scoring (includes `SeverityHyperparameterSpace`) |
| **Validation** | Quality metrics — topic diversity, outlier ratio, label uniqueness, Gini coefficient |
| **Registry** | MLflow experiments + safetensors model artifacts at `models/bertopic_{type}/latest/` |
| **Inference** | `TopicModelInference` loads saved models for real-time classification (backend + analytics + severity) |

See [data-pipeline/src/topic_modeling/README.md](data-pipeline/src/topic_modeling/README.md) for detailed documentation.

### Backend

FastAPI REST API with 17 endpoints, JWT auth, role-based access, and LangChain RAG.

| Area | Description |
|---|---|
| **Auth** | Signup (invite code for patients), login, token refresh, profile retrieval |
| **Patients** | List, get by ID, generate invite codes, list invite codes |
| **Journals** | List (role-aware), create (writes to staging for Airflow DAG 2) |
| **Conversations** | Paginated list with topic/severity/search filters |
| **Analytics** | Per-patient BERTopic topic distribution, frequency, date range, representative entries |
| **Dashboard** | Aggregate stats, mood trend data |
| **RAG Search** | Chat-style assistant with conversation history, vector search + Gemini LLM |

See [backend/README.md](backend/README.md) for full API reference.

### Frontend

Next.js 16 application with 15 routes, dark theme, and 175 Vitest tests.

| Area | Routes | Description |
|---|---|---|
| **Landing** | `/` | Hero, feature cards, stats, CTA |
| **Auth** | `/login`, `/signup` | Clean login form; 2-step signup with role selection (therapist/patient, invite code required for patients) |
| **Therapist Dashboard** | `/dashboard` | Overview with stat cards, patient list, per-patient BERTopic analytics, mood trends, RAG assistant panel |
| | `/dashboard/patients` | Patient grid with search, analytics badges, invite code dialog for onboarding |
| | `/dashboard/patients/[id]` | Patient profile — journal timeline with search/filter/sort/pagination, BERTopic topic distribution sidebar, monthly frequency, mood trend |
| | `/dashboard/conversations` | Conversation explorer with topic/severity badges, tab filtering |
| | `/dashboard/analytics` | Bias & distribution reports — BERTopic topics, severity, temporal patterns, patient distributions |
| | `/dashboard/search` | RAG chat assistant — conversation history, markdown rendering, split source display, turn limits |
| | `/dashboard/settings` | Therapist profile, pipeline status, embedding model info |
| **Patient Journal** | `/journal` | Entry composer with mood selector (1–5), word count, timeline with topic badges |
| | `/journal/insights` | Patient's own BERTopic analytics — topic distribution bars, monthly frequency chart, summary stats |
| | `/journal/prompts` | Therapist prompt cards with pending/answered states |
| | `/journal/settings` | Patient profile, linked therapist, privacy notice |

**Key design decisions:**
- Dark zinc theme via shadcn/ui (20+ components including Dialog for invite codes)
- Collapsible sidebar for therapist dashboard, top nav for patient journal
- API client (`src/lib/api.ts`) with typed fetch wrappers for all backend endpoints
- Auth context (`src/lib/auth-context.tsx`) with JWT token management, role-based redirect
- TypeScript domain types (`src/types/index.ts`) matching backend models

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, Lucide Icons, react-markdown |
| Frontend Testing | Vitest 4, React Testing Library, jsdom (175 tests across 18 files) |
| Backend | FastAPI, Motor (async MongoDB), python-jose (JWT), passlib (bcrypt), pydantic-settings |
| Backend Testing | pytest, pytest-asyncio, httpx (144 tests across 10 files) |
| RAG | LangChain (langchain-google-genai, langchain-huggingface, langchain-mongodb), sentence-transformers |
| Data Pipeline | Python, Pandas, NumPy, Apache Airflow, Docker Compose |
| Topic Modeling | BERTopic (>=0.17.0), Gemini LLM labeling, UMAP, HDBSCAN |
| Experiment Tracking | MLflow (>=3.0.0), local file-backed |
| ML/Embedding | Sentence-Transformers (`all-MiniLM-L6-v2`, 384 dims) |
| LLM | Google Gemini API (`gemini-2.5-flash`) |
| Storage | MongoDB Atlas (vector search + raw collections + staging + analytics) |
| Data Versioning | DVC + Google Cloud Storage |
| Pipeline Testing | pytest (322 tests across 15 files, mocked external services) |
| CI/CD | GitHub Actions (lint, test, build, Docker validation) |

## Testing

641 tests across all three components:

```bash
# data pipeline (322 tests across 15 files)
cd data-pipeline
pytest tests/ -v --cov

# backend (144 tests across 10 files)
cd backend
pytest tests/ -v --cov

# frontend (175 tests across 18 files)
cd frontend
npm test
npm run test:coverage
```

All external services (HuggingFace, Gemini API, MongoDB, sentence-transformers, BERTopic) are mocked in tests.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | Description |
|---|---|
| **Data Pipeline Tests** | Python 3.10, installs dependencies, runs 322 pytest tests |
| **Backend Tests** | Python 3.10, installs dependencies, runs 144 pytest tests |
| **Frontend Tests & Build** | Node 20, lint, 175 Vitest tests, production build |
| **Docker Build** | Validates the Airflow Docker image builds successfully |
| **CI Pass** | Gates the pipeline — fails if any job fails |

## Contributing

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature
   ```
2. Make your changes and ensure tests pass:
   ```bash
   cd data-pipeline && pytest tests/ -v
   cd backend && pytest tests/ -v
   cd frontend && npm test
   ```
3. Commit and push:
   ```bash
   git commit -m "Add your feature"
   git push origin feature/your-feature
   ```
4. Open a Pull Request to merge into `main`

### Guidelines

- Preserve clinical language in all text processing (no stopword removal, no lowercasing)
- Frame all AI outputs as "retrieved information" — never as advice or diagnosis
- Include source citations in any RAG responses
- Mock all external services in tests
- Use the centralized `Settings` dataclass from `configs/config.py` for all configuration