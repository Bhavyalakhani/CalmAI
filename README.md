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
│   ├── tests/              #   199 pytest tests
│   ├── configs/            #   Configuration and patient profiles
│   ├── data/               #   Raw, processed, and embedded data
│   ├── reports/            #   Bias and schema validation reports
│   ├── docker-compose.yaml #   Full Airflow cluster (6 containers)
│   ├── Dockerfile          #   Custom Airflow image
│   ├── dvc.yaml            #   DVC pipeline stages for reproducibility
│   └── run_pipeline.py     #   Local runner (no Airflow)
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
├── frontend/               # Web application (PLANNED)
│                           #   Therapist dashboard
│                           #   Patient journaling interface
│
├── docs/                   # Project documentation
├── assets/                 # Static assets
└── logs/                   # Application logs
```

## Quick Start

### Prerequisites

- Python 3.10+
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

### Run Tests

```bash
cd data-pipeline
pytest tests/ -v              # 199 tests
pytest tests/ -v --cov        # With coverage
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

### Frontend (Planned)

- Therapist dashboard with timeline, topic, and trend views
- Patient journaling interface
- RAG-powered natural language query interface

## Tech Stack

| Layer | Technologies |
|---|---|
| Data Pipeline | Python, Pandas, NumPy, Apache Airflow, Docker Compose |
| ML/Embedding | Sentence-Transformers, HuggingFace Datasets |
| LLM | Google Gemini API (`gemini-2.5-flash`) (Temporary for now, will be upgraded later)|
| Storage | MongoDB Atlas (vector search + raw collections) |
| Data Versioning | DVC + Google Cloud Storage |
| Testing | pytest (199 tests, mocked external services) |
| CI/CD | Docker, DVC |

## Contributing

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature
   ```
2. Make your changes and ensure tests pass:
   ```bash
   cd data-pipeline && pytest tests/ -v
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