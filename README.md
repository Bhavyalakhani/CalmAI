# CalmAI

A B2B SaaS platform for licensed therapists - helps mental health professionals organize, retrieve, and reason over patient journal data using RAG and semantic search. All clinical judgment stays with humans.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Components](#components)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)

## Overview

CalmAI consists of two main modules:

1. **Patient Journaling Module** - Patients write journal entries, receive analytical insights, and respond to therapist-assigned prompts
2. **Therapist Dashboard** - Timeline view, topic modeling, trend analysis, and a RAG assistant for natural language queries over patient data

The platform **never makes diagnoses or treatment recommendations** - it surfaces information so therapists can make better-informed clinical decisions.

## System Architecture

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────────┐
│   Frontend   │────►│   Backend    │────►│    MongoDB Atlas       │
│  (React/Next)│◄────│  (FastAPI)   │◄────│  (Vector Store + Raw) │
└──────────────┘     └──────┬───────┘     └───────────┬───────────┘
                            │                         │
                            │                         │
                     ┌──────▼───────┐          ┌──────▼──────┐
                     │    Models    │          │    Data     │
                     │  (BERTopic,  │          │  Pipeline   │
                     │  Fine-tuned  │          │  (Airflow)  │
                     │  Embeddings) │          └─────────────┘
                     └──────────────┘
```

## Project Structure

```
CalmAI/
├── data-pipeline/          # Data acquisition, processing, and storage (ACTIVE)
│   ├── dags/               #   Airflow DAG definitions (2 DAGs)
│   ├── src/                #   Pipeline source code (9 modules)
│   ├── tests/              #   205 pytest tests
│   ├── configs/            #   Configuration and patient profiles
│   ├── data/               #   Raw, processed, and embedded data
│   ├── reports/            #   Bias and schema validation reports
│   ├── docker-compose.yaml #   Full Airflow cluster (6 containers)
│   ├── Dockerfile          #   Custom Airflow image
│   ├── dvc.yaml            #   DVC pipeline stages for reproducibility
│   └── run_pipeline.py     #   Local runner (no Airflow)
│
├── frontend/               # Web application (ACTIVE)
│   ├── src/
│   │   ├── app/            #   Next.js App Router (14 routes)
│   │   │   ├── page.tsx            # Landing page
│   │   │   ├── login/              # Login page
│   │   │   ├── signup/             # 2-step signup (role selection → form)
│   │   │   ├── dashboard/          # Therapist dashboard (6 sub-routes)
│   │   │   │   ├── page.tsx        #   Overview — stats, patient list, analytics, RAG panel
│   │   │   │   ├── patients/       #   Patient grid with search
│   │   │   │   ├── conversations/  #   Conversation explorer with topic/severity
│   │   │   │   ├── analytics/      #   Bias reports & distribution charts
│   │   │   │   ├── search/         #   RAG search with generated answers
│   │   │   │   └── settings/       #   Profile & pipeline status
│   │   │   └── journal/            # Patient journal (4 sub-routes)
│   │   │       ├── page.tsx        #   Entry composer, mood selector, timeline
│   │   │       ├── insights/       #   Theme distribution, frequency charts
│   │   │       ├── prompts/        #   Therapist prompts & responses
│   │   │       └── settings/       #   Patient profile & privacy
│   │   ├── components/ui/  #   shadcn/ui components (20+)
│   │   ├── lib/            #   Utilities (cn) and mock data
│   │   └── types/          #   TypeScript domain types
│   ├── vitest.config.ts    #   Vitest configuration (jsdom, React)
│   └── package.json
│
├── models/                 # Model training and evaluation (PLANNED)
│                           #   BERTopic for topic modeling
│                           #   Fine-tuned embedding model
│
├── backend/                # API server (PLANNED)
│                           #   FastAPI REST API
│                           #   RAG retrieval endpoints
│                           #   Authentication and authorization
│
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
cd data-pipeline
cp .env.example .env
# Edit .env with your API keys and MongoDB URI

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

### Run the Frontend

```bash
cd frontend
npm install
npm run dev                   # Start dev server at http://localhost:3000
npm run build                 # Production build
```

### Run Tests

```bash
# Data pipeline tests
cd data-pipeline
pytest tests/ -v              # 205 tests
pytest tests/ -v --cov        # With coverage

# Frontend tests
cd frontend
npm test                      # 127 Vitest tests (17 test files)
npm run test:watch            # Watch mode
npm run test:coverage         # With coverage report
```

## Components

### Data Pipeline (Active)

The data pipeline is fully implemented and handles the complete data lifecycle:

| Stage | Description |
|---|---|
| **Acquisition** | Downloads 2 HuggingFace datasets + generates 1,000 synthetic journals via Gemini API |
| **Preprocessing** | Domain-specific text cleaning that preserves clinical language markers |
| **Validation** | Expectation-based schema validation with a pipeline gate (halts on failure) |
| **Bias Detection** | Topic/severity/theme analysis with visualizations and underrepresentation flagging |
| **Embedding** | 384-dim vectors from `sentence-transformers/all-MiniLM-L6-v2` |
| **Storage** | MongoDB Atlas with unified `rag_vectors` collection for vector search |
| **Orchestration** | 2 Airflow DAGs - batch pipeline + incoming journal micro-batch |
| **Versioning** | DVC with GCS remote for full artifact reproducibility |

See [data-pipeline/README.md](data-pipeline/README.md) for comprehensive documentation.

### Models (Planned)

- **BERTopic** for automatic topic modeling over journal entries
- **Fine-tuned embedding model** to replace `all-MiniLM-L6-v2` for domain-specific retrieval
- Patient analytics and trend detection

### Backend (Planned)

- FastAPI REST API
- RAG retrieval endpoints with source citations
- Patient/therapist authentication
- Journal CRUD operations

### Frontend (Active)

The frontend is a fully built Next.js 16 application with 14 routes, dark theme, and 127 Vitest tests.

| Area | Routes | Description |
|---|---|---|
| **Landing** | `/` | Hero, feature cards, stats, CTA |
| **Auth** | `/login`, `/signup` | Clean login form; 2-step signup with role selection (therapist/patient) |
| **Therapist Dashboard** | `/dashboard` | Overview with stat cards, patient list, per-patient analytics, mood trends, RAG assistant panel |
| | `/dashboard/patients` | Patient grid with search, analytics badges, onboarding dates |
| | `/dashboard/conversations` | Conversation explorer with topic/severity badges, tab filtering |
| | `/dashboard/analytics` | Bias & distribution reports — topic, severity, theme, temporal, patient distributions |
| | `/dashboard/search` | RAG search with patient/source filters, suggestion chips, generated answers with citations |
| | `/dashboard/settings` | Therapist profile, pipeline status, embedding model info |
| **Patient Journal** | `/journal` | Entry composer with mood selector (1–5), word count, timeline with theme badges |
| | `/journal/insights` | Analytics — theme distribution bars, monthly frequency chart, disclaimer |
| | `/journal/prompts` | Therapist prompt cards with pending/answered states |
| | `/journal/settings` | Patient profile, linked therapist, privacy notice |

**Key design decisions:**
- Dark zinc theme via shadcn/ui (20+ components)
- Collapsible sidebar for therapist dashboard, top nav for patient journal
- Mock data layer (`src/lib/mock-data.ts`) aligned with MongoDB schema from the data pipeline
- TypeScript domain types (`src/types/index.ts`) matching pipeline collections

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, Lucide Icons |
| Frontend Testing | Vitest 4, React Testing Library, jsdom (127 tests across 17 files) |
| Data Pipeline | Python, Pandas, NumPy, Apache Airflow, Docker Compose |
| ML/Embedding | Sentence-Transformers, HuggingFace Datasets |
| LLM | Google Gemini API (`gemini-2.5-flash`) (Temporary for now, will be upgraded later)|
| Storage | MongoDB Atlas (vector search + raw collections) |
| Data Versioning | DVC + Google Cloud Storage |
| Pipeline Testing | pytest (199 tests, mocked external services) |
| CI/CD | Docker, DVC |

## Contributing

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature
   ```
2. Make your changes and ensure tests pass:
   ```bash
   cd data-pipeline && pytest tests/ -v
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
- Frame all AI outputs as "retrieved information" - never as advice or diagnosis
- Include source citations in any RAG responses
- Mock all external services in tests
- Use the centralized `Settings` dataclass from `configs/config.py` for all configuration