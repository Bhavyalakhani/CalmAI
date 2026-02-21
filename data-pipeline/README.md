# CalmAI Data Pipeline

An end-to-end data pipeline for the CalmAI platform - acquires, preprocesses, validates, analyzes, embeds and stores mental health conversation and journal data into a unified MongoDB vector store for RAG-powered retrieval and analytics.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Running the Pipeline](#running-the-pipeline)
  - [Option A - Docker (Airflow)](#option-a--docker-airflow)
  - [Option B - Local Runner](#option-b--local-runner)
- [Code Structure](#code-structure)
- [Pipeline Stages](#pipeline-stages)
- [Pipeline Flow Optimization](#pipeline-flow-optimization)
- [Airflow DAGs](#airflow-dags)
- [Data Versioning with DVC](#data-versioning-with-dvc)
- [MongoDB Schema](#mongodb-schema)
- [Testing](#testing)
- [Reproducibility](#reproducibility)
- [Environment Variables](#environment-variables)

---

## Overview

CalmAI is a **B2B SaaS platform for licensed therapists** - not a patient-facing therapy tool. This data pipeline is the foundational component that:

1. **Acquires** data from two HuggingFace conversation datasets and generates synthetic patient journals via the Gemini API
2. **Preprocesses** text with domain-specific rules that preserve clinical language (no stopword removal, no lowercasing)
3. **Validates** schema integrity with expectation-based checks and a validation gate that halts the pipeline on failure
4. **Detects bias** across topics, severity levels, themes, and temporal patterns with visualizations
5. **Embeds** all text using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) (Temporary for dev, will be upgraded later)
6. **Stores** everything in MongoDB Atlas with a unified `rag_vectors` collection for vector search

All clinical judgment stays with human therapists - the system surfaces information but never makes diagnoses or treatment recommendations.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Apache Airflow (Docker)                         │
│                                                                        │
│   DAG 1: calm_ai_data_pipeline (manual trigger, batch)                 │
│   ┌───────┐   ┌──────────┐   ┌──────────┐   ┌──────┐   ┌───────────┐  │
│   │Acquire├──►│Preprocess├──►│ Validate ├──►│ Bias ├──►│  Embed    │  │
│   └───────┘   └──────────┘   └────┬─────┘   └──────┘   └─────┬─────┘  │
│                                   │ gate                      │        │
│                              pass/fail                        ▼        │
│                                              ┌─────────┐  ┌───────┐   │
│                                              │ MongoDB  │◄─┤ Store │   │
│                                              │  Atlas   │  └───┬───┘   │
│   DAG 2: incoming_journals_pipeline          │          │      │       │
│   (*/30 * * * *, incremental append)         │          │      ▼       │
│   ┌───────┐  ┌────────┐  ┌───────┐  ┌─────┐ │          │  ┌───────┐   │
│   │ Fetch ├─►│Validate├─►│ Embed ├─►│Store├►│          │  │ Email │   │
│   └───────┘  └────────┘  └───────┘  └─────┘ └──────────┘  └───────┘   │
└─────────────────────────────────────────────────────────────────────────┘

External Services:
  • HuggingFace Datasets (conversation data)
  • Google Gemini API (synthetic journal generation)
  • MongoDB Atlas (vector store + raw collections)
  • GCS Bucket (DVC remote for artifact versioning)
```

### Tech Stack

| Component | Technology |
|---|---|
| Orchestration | Apache Airflow 2.8.1 (CeleryExecutor, Redis, PostgreSQL) |
| Containerization | Docker Compose (6 services) |
| ML/Data | Python, Pandas, NumPy, Sentence-Transformers |
| Storage | MongoDB Atlas (unified vector store) |
| LLM | Google Gemini `gemini-2.5-flash` (synthetic data generation) (Temporary for now, will be upgraded later) |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (384 dims) |
| Data Versioning | DVC + Google Cloud Storage |
| Testing | pytest (199 tests, 12 test files) |
| Alerts | SMTP email notifications on pipeline success |

## Prerequisites

- **Python 3.10+**
- **Docker Desktop** (with WSL 2 backend if on Windows)
- **Git**
- **MongoDB Atlas** account with a cluster and connection string
- **Google Gemini API key** for synthetic journal generation
- **(Optional)** GCS bucket + service account for DVC remote storage

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/CalmAI.git
cd CalmAI
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
cd data-pipeline
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```dotenv
# CalmAI
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true
MONGODB_DATABASE=calm_ai

# Airflow (only needed for Docker)
AIRFLOW_UID=50000
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

# SMTP (optional - for success emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=True
SMTP_SSL=False
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_MAIL_FROM=your-email@gmail.com
```

### 5. MongoDB Atlas Setup

1. Create a free cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a database user with read/write permissions
3. Whitelist your IP (or use `0.0.0.0/0` for development)
4. Copy the connection string to `MONGODB_URI` in `.env`
5. Create a vector search index on the `rag_vectors` collection via the Atlas UI:
   - **Field**: `embedding`
   - **Dimensions**: 384
   - **Similarity**: cosine

---

## Running the Pipeline

### Option A - Docker (Airflow)

This is the prod approach using the full Airflow cluster.

#### 1. Build the Docker Images

```bash
cd data-pipeline
docker compose build
```

This creates a custom image based on `apache/airflow:2.8.1-python3.10` with all Python dependencies installed.

#### 2. Initialize Airflow

```bash
docker compose up airflow-init
```

Wait for `airflow-init exited with code 0` - this runs database migrations and creates the admin user.

#### 3. Start the Cluster

```bash
docker compose up -d
```

This starts 6 containers:

| Container | Purpose |
|---|---|
| `postgres` | Airflow metadata database |
| `redis` | Celery message broker |
| `airflow-webserver` | Web UI on `http://localhost:8080` |
| `airflow-scheduler` | Schedules and monitors DAG runs |
| `airflow-worker` | Executes tasks via Celery |
| `airflow-triggerer` | Handles deferred/async triggers |

#### 4. Trigger the Pipeline

1. Open `http://localhost:8080` (login: `airflow` / `airflow`)
2. Unpause `calm_ai_data_pipeline`
3. Click the play button → **Trigger DAG**
4. Monitor progress in the **Graph** view

#### 5. Useful Docker Commands

```bash
docker compose ps                                    # Check container status
docker compose logs airflow-worker --tail 50          # Worker logs
docker compose down                                   # Stop (keep data)
docker compose down -v                                # Stop + delete all data
docker compose build && docker compose up -d          # Rebuild after changes
```

### Option B - Local Runner

For development and debugging without Docker/Airflow:

```bash
cd data-pipeline
python run_pipeline.py
```

This runs all 9 pipeline steps sequentially with timing:

| Step | Description |
|---|---|
| 1 | Download HuggingFace conversation datasets |
| 2 | Generate synthetic journals via Gemini API |
| 3 | Preprocess conversations |
| 4 | Preprocess journals |
| 5 | Validate data (halts on failure) |
| 6 | Bias analysis - conversations |
| 7 | Bias analysis - journals |
| 8 | Embed conversations + journals |
| 9 | Store to MongoDB |

At the end, a summary table shows duration per step and the total runtime.

---

## Code Structure

```
data-pipeline/
├── configs/
│   ├── config.py                    # Central Settings dataclass (paths, env vars)
│   └── patient_profiles.yaml        # 10 patient profiles for journal generation
│
├── dags/
│   ├── calm_ai_pipeline.py          # DAG 1 - batch pipeline (manual trigger)
│   └── incoming_journals_pipeline.py # DAG 2 - incoming journals (*/30 * * * *)
│
├── src/
│   ├── acquisition/
│   │   ├── data_downloader.py       # Downloads 2 HuggingFace datasets
│   │   └── generate_journals.py     # Generates journals via Gemini API
│   │
│   ├── preprocessing/
│   │   ├── base_preprocessor.py     # Shared text cleaning (unicode, URLs, emails)
│   │   ├── conversation_preprocessor.py  # Conversation-specific processing
│   │   └── journal_preprocessor.py  # Journal-specific processing + temporal features
│   │
│   ├── validation/
│   │   └── schema_validator.py      # Expectation-based schema validation
│   │
│   ├── bias_detection/
│   │   ├── slicer.py                # Generic data slicing utilities
│   │   ├── conversation_bias.py     # Topic, severity, response quality analysis
│   │   └── journal_bias.py          # Theme, temporal, patient distribution analysis
│   │
│   ├── embedding/
│   │   └── embedder.py              # Sentence-transformer embedding generation
│   │
│   ├── storage/
│   │   └── mongodb_client.py        # MongoDB operations (CRUD, indexes, batch inserts)
│   │
│   ├── analytics/
│   │   └── patient_analytics.py     # Per-patient analytics and theme classification
│   │
│   └── alerts/
│       └── success_email.py         # HTML success email with task durations
│
├── tests/                           # 199 tests across 12 files
│   ├── conftest.py                  # Shared fixtures and mock settings
│   ├── test_data_downloader.py
│   ├── test_generate_journals.py
│   ├── test_conversation_preprocessor.py
│   ├── test_journal_preprocessor.py
│   ├── test_schema_validator.py
│   ├── test_slicer.py
│   ├── test_conversation_bias.py
│   ├── test_journal_bias.py
│   ├── test_embedding.py
│   ├── test_storage.py
│   └── test_incoming_pipeline.py
│
├── data/
│   ├── raw/                         # Downloaded and generated raw data
│   │   ├── conversations/           # HuggingFace parquets
│   │   └── journals/                # Synthetic journals + raw API responses
│   ├── processed/                   # Preprocessed + embedded parquets
│   │   ├── conversations/
│   │   └── journals/
│   └── embeddings/
│       └── incoming_journals/       # Runtime incoming journal embeddings
│
├── reports/
│   ├── bias/                        # JSON reports + PNG visualizations
│   ├── schema/                      # Schema validation JSON reports
│   └── validation/                  # Reserved for future validation reports
│
├── docker-compose.yaml              # Full Airflow cluster definition
├── Dockerfile                       # Custom Airflow image
├── requirements.txt                 # Python dependencies
├── run_pipeline.py                  # Local pipeline runner (no Airflow)
└── .env.example                     # Environment variable template
```

### Module Descriptions

| Module | Purpose |
|---|---|
| `data_downloader.py` | Downloads `Amod/mental_health_counseling_conversations` (~3,512 rows) and `nbertagnolli/counsel-chat` from HuggingFace. Validates row counts and column types. Saves as parquet. |
| `generate_journals.py` | Generates 100 journal entries per patient (10 patients) using Gemini API. 20–30 words each, spanning 300 days with 2–4 day gaps. Supports `run`, `fetch`, `parse` subcommands. |
| `base_preprocessor.py` | Unicode normalization (NFC), URL → `<URL>`, email → `<EMAIL>`, base64 image stripping, curly quote standardization, whitespace normalization. Preserves clinical language. |
| `conversation_preprocessor.py` | Merges two conversation datasets, deduplicates via MD5 hash (`context \|\|\| response`), computes text statistics, creates embedding text (`User concern: ...\n\nCounselor response: ...`). |
| `journal_preprocessor.py` | Parses and forward-fills dates, computes temporal features (`day_of_week`, `week_number`, `month`, `year`, `days_since_last`), creates date-prefixed embedding text. |
| `schema_validator.py` | Expectation-based validation: column existence, non-null checks, type checks, uniqueness, string non-empty, value ranges. Reports pass rate per dataset. Also validates incoming journals. |
| `slicer.py` | Generic keyword-based slicing utilities used by both bias analyzers. |
| `conversation_bias.py` | Classifies conversations into 10 topics and 4 severity levels. Flags underrepresented topics (<3%). Analyzes response length by topic. Generates visualizations. |
| `journal_bias.py` | Classifies journals into 8 themes. Analyzes temporal patterns (entries by day/month), patient distribution, and sparse patients (<10 entries). Generates visualizations. |
| `embedder.py` | Loads `sentence-transformers/all-MiniLM-L6-v2`, generates 384-dim embeddings in batches of 64. Separate functions for conversations, journals, and incoming journals. |
| `mongodb_client.py` | Batch inserts (500 docs/batch), index creation, collection management. Conversations/journals use clear+replace; incoming journals use append. Logs pipeline runs to `pipeline_metadata`. |
| `patient_analytics.py` | Per-patient theme classification using keyword matching across 8 themes. Computes analytics for the incoming journals pipeline. |
| `success_email.py` | Sends HTML email with task duration table, MongoDB collection stats, and pipeline summary on successful completion. |

---

## Pipeline Stages

### DAG 1 - Batch Pipeline (`calm_ai_data_pipeline`)

**Trigger**: Manual | **Mode**: Clear + Replace (idempotent)

```
start
├── download_conversations ──→ preprocess_conversations ──┐
└── generate_journals ──────→ preprocess_journals ────────┘
                                                           ↓
                                                  preprocessing_complete
                                                           ↓
                                                     validate_data
                                                           ↓
                                                   validation_branch
                                               ┌───────────┴───────────┐
                                          (pass)                  (fail)
                                    ┌────┴────┐            validation_failed
                             bias_conversations  bias_journals
                                    └────┬────┘
                                    bias_complete
                                    ┌────┴────┐
                             embed_conversations  embed_journals
                                    └────┬────┘
                                  embedding_complete
                                         ↓
                                   store_to_mongodb
                                         ↓
                                    success_email
                                         ↓
                                        end
```

### DAG 2 - Incoming Journals (`incoming_journals_pipeline`)

**Trigger**: Every 30 minutes | **Mode**: Incremental append

```
start → fetch_new_entries → preprocess_entries → validate_entries → embed_entries
  → store_to_mongodb → update_analytics → mark_processed → success_email → end
```

Uses a `ShortCircuitOperator` - if no new journal entries are found in MongoDB, the entire DAG run is skipped.

Overview — Incoming Journals Pipeline

The `incoming_journals_pipeline` is a compact, sequential micro-batch DAG that incrementally ingests new journal entries from the `incoming_journals` staging collection and updates the primary stores and per-patient analytics. Key behaviors and conventions:

- Tasks: `start` → `fetch_new_entries` → `preprocess_entries` → `validate_entries` → `embed_entries` → `store_to_mongodb` → `update_analytics` → `mark_processed` → `success_email`.
- In-memory preprocessing: `preprocess_entries` applies the same preprocessing and temporal feature engineering used by the batch pipeline but operates on the runtime records (no parquet I/O). It uses XCOM to pass the data to the tasks forward.
- XCom conventions: tasks push `duration` (float seconds) for runtime telemetry; `start` pushes a `run_id` (timestamp format YYYYMMDD_HHMMSS); `fetch_new_entries` pushes `journal_count`; embedding and storage tasks push sanitized, JSON-safe records and insert metrics.
- Safety: before pushing to XCom, non-JSON-native types (pandas Timestamps, numpy scalars/arrays) are converted to ISO strings, Python primitives or lists to ensure Airflow's JSON XCom serialization works reliably.
- Notifications and auditing: `store_to_mongodb` records run metadata and collection stats in `pipeline_metadata`; `success_email` sends a concise run summary (durations, counts, insert results) to the configured recipients.

The pipeline is intentionally sequential and idempotent for the micro-batch use case — `max_active_runs=1` prevents overlapping runs and `mark_processed` records prevent reprocessing of the same entries.

---

## Pipeline Flow Optimization

The pipeline is designed for maximum throughput through parallelism, synchronization points and runtime tracking.

### Parallelism Strategy

The DAG exploits four parallel execution branches in the batch pipeline:

| Stage | Parallel Tasks | Rationale |
|---|---|---|
| Acquisition | `download_conversations` \|\| `generate_journals` | Independent data sources (HuggingFace vs Gemini API) |
| Preprocessing | `preprocess_conversations` \|\| `preprocess_journals` | Each operates on its own dataset with no shared state |
| Bias Detection | `bias_conversations` \|\| `bias_journals` | Separate analyzers, separate reports |
| Embedding | `embed_conversations` \|\| `embed_journals` | Independent embedding batches with no cross-dependency |

The incoming journals DAG (DAG 2) is intentionally sequential since each step depends on the previous output, and `max_active_runs=1` prevents overlapping runs.

### Synchronization Points

Three `EmptyOperator` nodes act as synchronization barriers:

- **`preprocessing_complete`** - waits for both preprocessors before validation
- **`bias_complete`** - waits for both bias analyzers before embedding
- **`embedding_complete`** - waits for both embedders before MongoDB storage

This ensures downstream tasks never execute on partial data.

### Bottleneck Analysis via Airflow Gantt Chart

The Airflow UI Gantt chart (accessible at **Browse → Task Instances → Gantt**) was used to identify bottlenecks across pipeline runs:

- **Embedding tasks** are the most time-intensive stage (~60-70% of total runtime) due to sentence-transformer model inference. This is expected and acceptable since the model runs on CPU within Docker.
- **Journal generation** (Gemini API) has variable latency depending on API response times and rate limits, but runs in parallel with conversation download so it does not block the critical path.
- **MongoDB storage** is optimized with batch inserts (500 docs per batch) and `BulkWriteError` handling for partial failures, keeping this stage fast.
- **Validation and bias detection** are lightweight and complete quickly.

### Task Duration Tracking

Every task records its execution duration via XCom:

```python
kwargs['ti'].xcom_push(key='duration', value=round(duration, 2))
```

The `store_to_mongodb` task aggregates all task durations into the `pipeline_metadata` collection for historical analysis. The `success_email` task includes a task duration table in the HTML report, providing per-run performance visibility.

### Optimization Decisions

1. **CeleryExecutor** over SequentialExecutor - enables true parallel task execution across worker processes
2. **Batch inserts (500 docs)** - balances memory usage against insert throughput for MongoDB
3. **Parquet intermediate storage** - columnar format minimizes I/O between pipeline stages
4. **Idempotent tasks** - `skip_existing` pattern avoids redundant recomputation on retries
5. **Short-circuit operator** (DAG 2) - skips entire pipeline when no new data exists, saving compute
6. **Validation gate** (`BranchPythonOperator`) - halts pipeline early on schema failures, preventing wasted embedding/storage work

---

## Data Versioning with DVC

DVC (Data Version Control) tracks all data artifacts so the pipeline is fully reproducible. Artifacts are stored in a Google Cloud Storage bucket.

> **Note:** DVC files (`dvc.yaml`, `dvc.lock`, `.dvc/config`, `.dvcignore`) live in the **project root** (`CalmAI/`), not inside `data-pipeline/`. Each stage in `dvc.yaml` uses `wdir: data-pipeline` so all relative paths resolve correctly.

### Setup

```bash
# DVC is included in requirements.txt, already installed
# Initialize (already done — .dvc/ is at project root)
dvc init

# Configure remote (already configured in .dvc/config)
dvc remote add -d gcs_remote gs://calmai-dvc-storage/data-pipeline
```

### Pipeline Stages

The `dvc.yaml` (at project root) mirrors the Airflow DAG with 9 stages:

| Stage | Outputs |
|---|---|
| `download_conversations` | `data/raw/conversations/*.parquet` |
| `generate_journals` | `data/raw/journals/synthetic_journals.parquet` |
| `preprocess_conversations` | `data/processed/conversations/processed_conversations.parquet` |
| `preprocess_journals` | `data/processed/journals/processed_journals.parquet` |
| `validate` | `reports/schema/*.json` |
| `bias_conversations` | `reports/bias/conversation_bias_report.json` |
| `bias_journals` | `reports/bias/journal_bias_report.json` |
| `embed_conversations` | `data/processed/conversations/embedded_conversations.parquet` |
| `embed_journals` | `data/processed/journals/embedded_journals.parquet` |

### Commands

```bash
# Reproduce the full pipeline (runs only changed stages)
dvc repro

# Snapshot current artifact state
dvc commit --force

# Push artifacts to GCS
dvc push

# Pull artifacts from GCS (on another machine)
dvc pull

# Check status of tracked files
dvc status
```

### How It Works

- `dvc.yaml` declares each stage's command, dependencies (`deps`), and outputs (`outs`)
- `dvc.lock` stores MD5 hashes of all deps and outs - this is committed to Git
- Actual data files (parquets, JSONs, PNGs) are in `.gitignore` - Git only tracks their hashes
- `dvc repro` compares current hashes to `dvc.lock` and only re-runs stages with changed inputs
- `dvc push` / `dvc pull` syncs artifacts to/from the GCS bucket

> **Note**: DVC runs standalone (CLI) and is not part of the Airflow DAGs. This is standard practice, Airflow handles orchestration, DVC handles artifact versioning and reproducibility.

---

## MongoDB Schema

### Collections (6)

| Collection | Purpose |
|---|---|
| `rag_vectors` | Unified vector store for RAG retrieval. Contains both conversations and journals with `doc_type` discriminator. |
| `conversations` | Raw + processed conversation data with text statistics. |
| `journals` | Raw + processed journal data with temporal features. |
| `pipeline_metadata` | Execution audit trail - run IDs, task durations, insert counts. |
| `incoming_journals` | Staging area for new patient journal entries (DAG 2 source). |
| `patient_analytics` | Per-patient theme classification and statistics (DAG 2 output). |

### Indexes

- `rag_vectors`: `doc_type`, `patient_id`, `therapist_id`, `conversation_id`, `journal_id`
- `conversations`: `conversation_id` (unique)
- `journals`: `journal_id` (unique), `patient_id`, `therapist_id`

### Vector Search

A vector search index must be created via the Atlas UI on `rag_vectors.embedding` with **cosine similarity** and **384 dimensions**.

---

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov --cov-report=term-missing

# Run a specific test file
pytest tests/test_embedding.py -v
```

### Test Summary (199 tests)

| Test File | Tests | Covers |
|---|---|---|
| `test_data_downloader.py` | 9 | HuggingFace download, validation, deduplication |
| `test_generate_journals.py` | 10 | Gemini API calls, JSON parsing, date generation |
| `test_conversation_preprocessor.py` | 9 | Text cleaning, dedup, embedding text creation |
| `test_journal_preprocessor.py` | 11 | Date parsing, temporal features, forward-fill |
| `test_schema_validator.py` | 19 | All expectation types, pass/fail reporting |
| `test_slicer.py` | 12 | Keyword slicing, threshold detection |
| `test_conversation_bias.py` | 9 | Topic classification, severity, visualizations |
| `test_journal_bias.py` | 9 | Theme classification, temporal analysis |
| `test_embedding.py` | 22 | Embedding generation, batch processing, incoming |
| `test_storage.py` | 30 | MongoDB CRUD, batch inserts, indexes, stats |
| `test_incoming_pipeline.py` | 20 | Validation, staging, analytics, end-to-end |
| `conftest.py` | - | Shared fixtures, mock settings |

All external services (HuggingFace, Gemini API, MongoDB, sentence-transformers) are mocked in tests.

---

## Reproducibility

### From a Fresh Clone

```bash
# 1. Clone and setup
git clone https://github.com/your-org/CalmAI.git
cd CalmAI
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r data-pipeline/requirements.txt

# 2. Configure
cd data-pipeline
cp .env.example .env
# Edit .env with your API keys and MongoDB URI

# 3a. Run locally
python run_pipeline.py

# 3b. OR run with Docker/Airflow
docker compose build
docker compose up airflow-init
docker compose up -d
# Trigger DAG from http://localhost:8080

# 4. Pull DVC artifacts (instead of regenerating)
dvc pull
```

### With DVC (Skip Computation)

If artifacts have been previously pushed to GCS, any team member can skip the computation-heavy steps:

```bash
dvc pull    # Downloads all parquets, reports, and embeddings from GCS
```

This gives you the exact same data artifacts as the original run, verified by MD5 hashes.

### Verification Checklist

- [ ] `rag_vectors` collection: ~3,700+ documents with `doc_type` field
- [ ] `conversations` and `journals` collections populated
- [ ] Vector search returns results via Atlas
- [ ] Bias reports in `reports/bias/` with visualization PNGs
- [ ] Schema reports in `reports/schema/` with pass/fail expectations
- [ ] All 199 tests passing (`pytest tests/ -v`)

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for journal generation |
| `GEMINI_MODEL` | No | Gemini model name (default: `gemini-2.5-flash`) |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | No | Database name (default: `calm_ai`) |
| `EMBEDDING_MODEL` | No | Sentence-transformers model (default: `all-MiniLM-L6-v2`) |
| `AIRFLOW_UID` | Docker | Airflow user ID (default: `50000`) |
| `SMTP_HOST` | No | SMTP server for email alerts |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASSWORD` | No | SMTP password / app password |
| `SMTP_MAIL_FROM` | No | Sender email address |
| `GOOGLE_APPLICATION_CREDENTIALS` | DVC | Path to GCS service account JSON key |
