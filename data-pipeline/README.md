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
- [GCS Model Storage](#gcs-model-storage)
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
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Apache Airflow (Docker)                            │
│                                                                             │
│  DAG 1: calm_ai_data_pipeline (manual trigger, batch, 23 tasks)             │
│  ┌───────┐   ┌──────────┐   ┌──────────┐   ┌───────┐   ┌─────┐   ┌──────┐ │
│  │Acquire├──►│Preprocess├──►│ Validate ├──►│ Embed ├──►│Train├──►│ Bias │ │
│  └───────┘   └──────────┘   └────┬─────┘   └───────┘   └──┬──┘   └──┬───┘ │
│                                  │ gate                    │         │      │
│                             pass/fail                      ▼         ▼      │
│                                             ┌─────────┐ ┌───────┐          │
│                                             │ MongoDB  │◄┤ Store │          │
│                                             │  Atlas   │ └───┬───┘          │
│  DAG 2: incoming_journals_pipeline          │(6 colls) │     │              │
│  (0 */12 * * *, incremental append)         │          │     ▼              │
│  ┌─────┐ ┌──────┐ ┌────┐ ┌─────┐ ┌─────┐   │          │ ┌───────┐          │
│  │Fetch├►│Prepro├►│Val.├►│Embed├►│Store├──►│          │ │ Email │          │
│  └─────┘ └──────┘ └────┘ └─────┘ └──┬──┘   └──────────┘ └───────┘          │
│                                     ▼                                       │
│                    ┌─────────┐  ┌──────┐  ┌───────┐                         │
│                    │Analytics├─►│ Mark ├─►│ Email │                         │
│                    └─────────┘  └──────┘  └───────┘                         │
└──────────────────────────────────────────────────────────────────────────────┘

External Services:
  • HuggingFace Datasets (conversation data)
  • Google Gemini API (synthetic journal generation)
  • MongoDB Atlas (vector store + raw collections)
  • GCS Bucket (versioned model artifact storage)
```

### Tech Stack

| Component | Technology |
|---|---|
| Orchestration | Apache Airflow 2.8.1 (CeleryExecutor, Redis, PostgreSQL) |
| Containerization | Docker Compose (6 services) |
| ML/Data | Python, Pandas, NumPy, Sentence-Transformers |
| Topic Modeling | BERTopic (>=0.17.0), Gemini LLM labeling, three independent models (journals, conversations, severity) |
| Experiment Tracking | MLflow (>=3.0.0), supports file-backed or SQLite + Model Registry |
| Model Lifecycle | Holdout validation, selection gates, bias gates, promotion, rollback |
| Storage | MongoDB Atlas (unified vector store) |
| LLM | Google Gemini `gemini-2.5-flash` (synthetic data generation) (Temporary for now, will be upgraded later) |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (384 dims) |
| Model Storage | Google Cloud Storage (versioned promoted/rejected uploads via `calm-ai-bucket-key.json`) |
| Data Versioning | DVC + Google Cloud Storage |
| Testing | pytest (367 tests, 19 test files) |
| Alerts | SMTP email notifications on pipeline success |

## Prerequisites

- **Python 3.10+**
- **Docker Desktop** (with WSL 2 backend if on Windows)
- **Git**
- **MongoDB Atlas** account with a cluster and connection string
- **Google Gemini API key** for synthetic journal generation
- **(Optional)** GCS bucket + service account key (`calm-ai-bucket-key.json`) for model artifact uploads

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
5. The vector search index on `rag_vectors` is created automatically by `python src/storage/mongodb_client.py create-indexes`. Alternatively, create it manually via the Atlas UI:
   - **Index name**: `vector_index`
   - **Collection**: `rag_vectors`
   - **Field**: `embedding`
   - **Dimensions**: 384
   - **Similarity**: cosine
   - **Filter fields**: `patient_id`, `doc_type`

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

# batch pipeline (DAG 1) — full acquire → preprocess → validate → embed → train → store
python run_calm_ai_pipeline.py

# incoming journals pipeline (DAG 2) — micro-batch processing
python run_incoming_pipeline.py               # process unprocessed entries
python run_incoming_pipeline.py --seed         # seed test entries + process
python run_incoming_pipeline.py --seed-only    # only seed test entries
python run_incoming_pipeline.py --verify-only  # just check db state
python run_incoming_pipeline.py --force-retrain # force model retrain
python run_incoming_pipeline.py --skip-retrain  # skip retrain check
```

#### Batch Pipeline (`run_calm_ai_pipeline.py`)

Runs all 14 pipeline steps sequentially with timing:

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
| 9 | Train journal topic model (BERTopic) |
| 10 | Train conversation topic model (BERTopic) |
| 11 | Train severity model (BERTopic) |
| 12 | Store to MongoDB (+ classify conversations with topics & severity) |
| 13 | Compute patient analytics (per-patient topic distribution) |
| 14 | Model lifecycle — holdout validation, bias gate, selection policy, smoke test |
| 15 | GCS upload — promoted models to `promoted/v_YYYYMMDD_HHMMSS/` + `latest/`, rejected to `rejected/v_YYYYMMDD_HHMMSS/` |
| 14 | DVC version tracking (`dvc commit --force` + `dvc push`) |

At the end, a summary table shows duration per step and the total runtime.

#### Incoming Pipeline (`run_incoming_pipeline.py`)

Mirrors Airflow DAG 2 locally. Fetches unprocessed journals from `incoming_journals`, preprocesses, validates, embeds, stores to MongoDB, conditionally retrains BERTopic models, updates per-patient analytics, and marks entries as processed. Supports seeding test entries for development and a `--verify-only` mode to inspect current DB state without processing.

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
│   └── incoming_journals_pipeline.py # DAG 2 - incoming journals (0 */12 * * *)
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
│   │   ├── journal_bias.py          # Theme, temporal, patient distribution analysis
│   │   ├── holdout_bias_gate.py     # Holdout bias gate for model promotion decisions
│   │   └── severity.py              # BERTopic severity singleton wrapper (classify_severity)
│   │
│   ├── embedding/
│   │   └── embedder.py              # Sentence-transformer embedding generation
│   │
│   ├── storage/
│   │   └── mongodb_client.py        # MongoDB operations (CRUD, indexes, batch inserts)
│   │
│   ├── analytics/
│   │   └── patient_analytics.py     # Per-patient analytics (BERTopic model required)
│   │
│   ├── topic_modeling/
│   │   ├── __init__.py              # Public API exports
│   │   ├── config.py                # TopicModelConfig — shared BERTopic + MLflow settings
│   │   ├── experiment_tracker.py    # ExperimentTracker — MLflow tracking + Model Registry
│   │   ├── trainer.py               # TopicModelTrainer — BERTopic training with Gemini LLM labeling
│   │   ├── inference.py             # TopicModelInference — topic prediction from saved models
│   │   ├── validation.py            # TopicModelValidator — clustering metrics, holdout evaluation
│   │   ├── selection_policy.py      # SelectionPolicy — hard gates + weighted scoring for promotion
│   │   ├── rollback.py              # ModelRollback — automatic/manual rollback + smoke tests
│   │   └── bias_analysis.py         # TopicBiasAnalyzer — bias detection using BERTopic topics
│   │
│   └── alerts/
│       └── success_email.py         # HTML success email with task durations
│
├── tests/                           # Tests across 19 files
│   ├── conftest.py                  # Shared fixtures and mock settings
│   ├── test_data_downloader.py
│   ├── test_generate_journals.py
│   ├── test_conversation_preprocessor.py
│   ├── test_journal_preprocessor.py
│   ├── test_preprocessing.py
│   ├── test_schema_validator.py
│   ├── test_slicer.py
│   ├── test_conversation_bias.py
│   ├── test_journal_bias.py
│   ├── test_embedding.py
│   ├── test_storage.py
│   ├── test_analytics.py
│   ├── test_incoming_pipeline.py
│   ├── test_topic_modeling.py       # BERTopic trainer + inference tests
│   ├── test_topic_bias.py           # Topic-based bias analysis tests
│   ├── test_model_selection.py      # Selection policy hard gates + scoring tests
│   ├── test_holdout_bias_gate.py    # Holdout bias gate tests
│   ├── test_validation_lifecycle.py # Clustering metrics, holdout, comparison tests
│   └── test_model_registry.py       # MLflow registry + rollback + smoke tests
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
├── models/
│   └── bertopic_{type}/             # BERTopic model artifacts (journals, conversations, severity)
│       └── latest/model             # Safetensors serialization
│
├── mlruns/                          # MLflow experiment tracking (local file-backed)
│
├── reports/
│   ├── bias/                        # JSON reports + PNG visualizations
│   ├── schema/                      # Schema validation JSON reports
│   └── validation/                  # Reserved for future validation reports
│
├── docker-compose.yaml              # Full Airflow cluster definition
├── Dockerfile                       # Custom Airflow image
├── requirements.txt                 # Python dependencies
├── run_calm_ai_pipeline.py          # Local batch pipeline runner (DAG 1, no Airflow)
├── run_incoming_pipeline.py         # Local incoming pipeline runner (DAG 2, no Airflow)
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
| `slicer.py` | Generic slicing utilities used by both bias analyzers. |
| `conversation_bias.py` | Uses `TopicModelInference(model_type="conversations")` (model required). Classifies conversations into topics and 4 severity levels via BERTopic severity model. Flags underrepresented topics (<3%). Analyzes response length by topic. Generates visualizations. |
| `journal_bias.py` | Uses `TopicModelInference(model_type="journals")` (model required). Classifies journals into topics. Analyzes temporal patterns (entries by day/month), patient distribution, and sparse patients (<10 entries). Generates visualizations. |
| `severity.py` | BERTopic severity singleton wrapper. Lazy-loads `TopicModelInference(model_type="severity")` once, exposes `classify_severity()`, `classify_severity_batch()`, `classify_severity_series()`. Returns `"unknown"` when model is unavailable. Used by `mongodb_client`, `conversation_bias`, and `bias_analysis`. |
| `embedder.py` | Loads `sentence-transformers/all-MiniLM-L6-v2`, generates 384-dim embeddings in batches of 64. Separate functions for conversations, journals, and incoming journals. |
| `mongodb_client.py` | Batch inserts (500 docs/batch), index creation, collection management. Conversations/journals use clear+replace; incoming journals use append. Logs pipeline runs to `pipeline_metadata`. |
| `patient_analytics.py` | Per-patient topic classification using `TopicModelInference(model_type="journals")`. Returns "unclassified" when model unavailable. Computes topic distribution, topics over time, representative entries, and frequency analytics. |
| `topic_modeling/` | BERTopic topic modeling module (9 files). `TopicModelTrainer` trains three independent models (journals, conversations, severity) with Gemini LLM labeling and MLflow experiment tracking. `TopicModelInference` handles prediction from saved models including severity classification. `TopicModelValidator` checks quality metrics and holdout validation. `SelectionPolicy` enforces hard gates + weighted scoring for promotion. `ModelRollback` + `smoke_test_model` handle post-promotion verification and automatic rollback. `TopicBiasAnalyzer` detects bias using BERTopic topics. Models saved locally to `models/bertopic_{type}/latest/model` (safetensors) and uploaded to GCS with versioned `promoted/`/`rejected/` structure. Full lifecycle: train → holdout validation (80/20 split) → bias gate → selection policy → smoke test → GCS upload. |
| `success_email.py` | Sends HTML email with task duration table, MongoDB collection stats, and pipeline summary on successful completion. |

---

## Pipeline Stages

### DAG 1 - Batch Pipeline (`calm_ai_data_pipeline`)

**Trigger**: Manual | **Mode**: Clear + Replace (idempotent) | **Tasks**: 23

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
                             embed_conversations  embed_journals
                                    └────┬────┘
                                  embedding_complete
                      ┌─────────────────┼─────────────────┐
               train_journal_model  train_conversation_model  train_severity_model
                      └─────────────────┼─────────────────┘
                                  training_complete
                               ┌────────┴────────┐
                        bias_conversations  bias_journals
                               └────────┬────────┘
                                   bias_complete
                                        ↓
                            compute_patient_analytics
                                        ↓
                                  store_to_mongodb
                                        ↓
                                   success_email
                                        ↓
                                       end
```

### DAG 2 - Incoming Journals (`incoming_journals_pipeline`)

**Trigger**: Every 12 hours | **Mode**: Incremental append

```
start → fetch_new_entries → preprocess_entries → validate_entries → embed_entries
  → store_to_mongodb → conditional_retrain → update_analytics → mark_processed → success_email → end
```

Uses a `ShortCircuitOperator` - if no new journal entries are found in MongoDB, the entire DAG run is skipped.

The `conditional_retrain` task checks whether BERTopic models need retraining based on two thresholds: 50+ new journal entries accumulated since last training (`RETRAIN_ENTRY_THRESHOLD`) or 7+ days since last training (`RETRAIN_MAX_DAYS`). If either condition is met, each model goes through the full lifecycle: **Train → Basic Validation → Holdout Validation (80/20 split) → Bias Gate → Selection Policy → Smoke Test → GCS Upload**. Promoted models are uploaded to `promoted/v_YYYYMMDD_HHMMSS/` + `latest/`; rejected models to `rejected/v_YYYYMMDD_HHMMSS/` for audit. Training metadata is persisted via `MongoDBClient.save_training_metadata()` in `pipeline_metadata` (with `type: "training_metadata"`). First run always saves baseline metadata.

Overview — Incoming Journals Pipeline

The `incoming_journals_pipeline` is a compact, sequential micro-batch DAG that incrementally ingests new journal entries from the `incoming_journals` staging collection and updates the primary stores and per-patient analytics. Key behaviors and conventions:

- Tasks: `start` → `fetch_new_entries` → `preprocess_entries` → `validate_entries` → `embed_entries` → `store_to_mongodb` → `conditional_retrain` → `update_analytics` → `mark_processed` → `success_email`.
- In-memory preprocessing: `preprocess_entries` applies the same preprocessing and temporal feature engineering used by the batch pipeline but operates on the runtime records (no parquet I/O). It uses XCOM to pass the data to the tasks forward.
- XCom conventions: tasks push `duration` (float seconds) for runtime telemetry; `start` pushes a `run_id` (timestamp format YYYYMMDD_HHMMSS); `fetch_new_entries` pushes `journal_count`; embedding and storage tasks push sanitized, JSON-safe records and insert metrics.
- Safety: before pushing to XCom, non-JSON-native types (pandas Timestamps, numpy scalars/arrays) are converted to ISO strings, Python primitives or lists to ensure Airflow's JSON XCom serialization works reliably.
- Notifications and auditing: `store_to_mongodb` records run metadata and collection stats in `pipeline_metadata`; `success_email` sends a concise run summary (durations, counts, insert results, retrain status) to the configured recipients.

The pipeline is intentionally sequential and idempotent for the micro-batch use case — `max_active_runs=1` prevents overlapping runs and `mark_processed` records prevent reprocessing of the same entries.

---

## Pipeline Flow Optimization

The pipeline is designed for maximum throughput through parallelism, synchronization points and runtime tracking.

### Parallelism Strategy

The DAG exploits five parallel execution branches in the batch pipeline:

| Stage | Parallel Tasks | Rationale |
|---|---|---|
| Acquisition | `download_conversations` \|\| `generate_journals` | Independent data sources (HuggingFace vs Gemini API) |
| Preprocessing | `preprocess_conversations` \|\| `preprocess_journals` | Each operates on its own dataset with no shared state |
| Bias Detection | `bias_conversations` \|\| `bias_journals` | Separate analyzers, separate reports |
| Embedding | `embed_conversations` \|\| `embed_journals` | Independent embedding batches with no cross-dependency |
| Training | `train_journal_model` \|\| `train_conversation_model` \|\| `train_severity_model` | Independent BERTopic models trained in parallel |

The incoming journals DAG (DAG 2) is intentionally sequential since each step depends on the previous output, and `max_active_runs=1` prevents overlapping runs.

### Synchronization Points

Four `EmptyOperator` nodes act as synchronization barriers:

- **`preprocessing_complete`** - waits for both preprocessors before validation
- **`embedding_complete`** - waits for both embedders before model training
- **`training_complete`** - waits for all three BERTopic trainers before bias analysis
- **`bias_complete`** - waits for both bias analyzers before patient analytics and MongoDB storage

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

## Model Lifecycle

The pipeline implements a complete model lifecycle for BERTopic topic models:

### Pipeline Flow

```
train_candidates → validate_candidates → holdout_validation → bias_gate → selection_decision
  → [pass] smoke_test → GCS upload (promoted/v_YYYYMMDD_HHMMSS/ + latest/) → done
  → [fail] GCS upload (rejected/v_YYYYMMDD_HHMMSS/) → alert
```

This lifecycle runs in all 4 pipeline files (2 DAGs + 2 local runners) with consistent logic.

### Validation Metrics

**Clustering quality** (computed on UMAP embeddings, outliers excluded):
- Silhouette Score — cohesion vs separation
- Calinski-Harabasz Index — between/within cluster dispersion
- Davies-Bouldin Index — average cluster similarity (lower is better)
- DBCV — density-based cluster validity (most principled for HDBSCAN)

**Agreement metrics** (candidate vs active on same holdout):
- NMI (Normalized Mutual Information)
- ARI (Adjusted Rand Index)
- V-measure (homogeneity + completeness)

### Promotion Gates

Hard gates (must all pass):
- `outlier_ratio <= 0.20`
- `silhouette_score >= 0.10`
- `topic_diversity >= 0.50`
- `bias_disparity_delta <= 0.10`

Then weighted composite score: candidate must beat active by margin (default `0.01`).

### MLflow Model Registry

When `MLFLOW_TRACKING_URI` is set to a SQLite or PostgreSQL URI, the pipeline uses MLflow Model Registry for versioned model management with stage transitions (Staging → Production → Archived).

### Rollback

Automatic rollback triggers on smoke test failure. Manual rollback available via `ModelRollback.rollback(model_name)`.

### Configuration

All thresholds are configurable via environment variables (see `.env.example`):
- `MODEL_MAX_OUTLIER_RATIO`, `MODEL_MIN_SILHOUETTE`, `MODEL_MIN_TOPIC_DIVERSITY`
- `MODEL_MAX_BIAS_DISPARITY`, `MODEL_PROMOTION_MIN_SCORE_DELTA`
- `ENABLE_MODEL_SELECTION_GATE`, `ENABLE_MODEL_PROMOTION`, `ENABLE_MODEL_ROLLBACK`

---

## GCS Model Storage

Trained BERTopic models are uploaded to a Google Cloud Storage bucket with versioned folder structure. This enables artifact traceability and rollback across both promoted and rejected models.

### GCS Folder Structure

```
gs://calm-ai_model_registry/models/bertopic/
├── bertopic_journals/
│   ├── promoted/
│   │   ├── v_20260322_143012/   # timestamped version
│   │   │   └── model/           # safetensors artifacts
│   │   └── ...
│   ├── rejected/
│   │   ├── v_20260322_120500/
│   │   │   └── model/
│   │   └── ...
│   └── latest/                  # always points to most recent promoted model
│       └── model/
├── bertopic_conversations/
│   └── (same structure)
└── bertopic_severity/
    └── (same structure)
```

### Setup

1. Place your GCS service account key as `data-pipeline/calm-ai-bucket-key.json` (gitignored)
2. The key file path is configured via `GCS_KEY_FILE` in `.env` (default: `./calm-ai-bucket-key.json`)
3. In Docker, the key is mounted read-only at `/run/secrets/gcs-key.json` via `docker-compose.yaml`

### How It Works

- After model training, the pipeline runs the full lifecycle: holdout validation → bias gate → selection policy → smoke test
- **Promoted models**: uploaded to `promoted/v_YYYYMMDD_HHMMSS/` AND `latest/`
- **Rejected models**: uploaded to `rejected/v_YYYYMMDD_HHMMSS/` only (kept for audit, not served)
- GCS upload is non-blocking — failures are logged but don't fail the pipeline
- If `MODEL_REGISTRY_BUCKET` is empty or the key file is missing, GCS upload is skipped silently

### Configuration

| Variable | Default | Description |
|---|---|---|
| `GCS_KEY_FILE` | `./calm-ai-bucket-key.json` | Path to GCS service account JSON key |
| `MODEL_REGISTRY_BUCKET` | `calm-ai_model_registry` | GCS bucket name (no `gs://` prefix) |
| `MODEL_REGISTRY_PREFIX` | `models/bertopic` | Path prefix inside the bucket |

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

- `rag_vectors`: `doc_type`, `patient_id`, `therapist_id`, `conversation_id`, `journal_id` + `vector_index` (Atlas vector search on `embedding`, 384 dims, cosine)
- `conversations`: `conversation_id` (unique)
- `journals`: `journal_id` (unique), `patient_id`, `therapist_id`
- `incoming_journals`: `journal_id` (unique), `patient_id`, `is_processed`
- `patient_analytics`: `patient_id` (unique)

### Vector Search

The vector search index (`vector_index`) is created automatically by `python src/storage/mongodb_client.py create-indexes` via `_ensure_vector_search_index()`. It uses cosine similarity on `rag_vectors.embedding` (384 dims) with filter fields for `patient_id` and `doc_type`. Can also be created manually via the Atlas UI.

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

### Test Summary (367 tests)

| Test File | Tests | Covers |
|---|---|---|
| `test_data_downloader.py` | 14 | HuggingFace download, validation, deduplication |
| `test_generate_journals.py` | 13 | Gemini API calls, JSON parsing, date generation |
| `test_conversation_preprocessor.py` | 14 | Text cleaning, dedup, embedding text creation |
| `test_journal_preprocessor.py` | 17 | Date parsing, temporal features, forward-fill |
| `test_preprocessing.py` | 2 | Cross-preprocessor integration tests |
| `test_schema_validator.py` | 32 | All expectation types, pass/fail reporting, incoming validation |
| `test_slicer.py` | 17 | Data slicing, threshold detection |
| `test_conversation_bias.py` | 21 | Topic classification, severity, visualizations |
| `test_journal_bias.py` | 22 | Theme classification, temporal analysis |
| `test_embedding.py` | 19 | Embedding generation, batch processing, incoming |
| `test_storage.py` | 32 | MongoDB CRUD, batch inserts, indexes, incoming, training metadata |
| `test_analytics.py` | 31 | Patient topic classification, analytics computation, frequency, date range |
| `test_incoming_pipeline.py` | 29 | Fetch, preprocess, validate, embed, store, retrain, mark processed |
| `test_topic_modeling.py` | 58 | BERTopic trainer, inference, validation, MLflow tracking |
| `test_topic_bias.py` | 17 | Topic-based bias analysis using BERTopic |
| `conftest.py` | - | Shared fixtures, mock settings, sample DataFrames |

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

# 3a. Run locally (batch pipeline)
python run_calm_ai_pipeline.py

# 3a-alt. Run incoming journals pipeline
python run_incoming_pipeline.py

# 3b. OR run with Docker/Airflow
docker compose build
docker compose up airflow-init
docker compose up -d
# Trigger DAG from http://localhost:8080

```

### Verification Checklist

- [ ] `rag_vectors` collection: ~3,700+ documents with `doc_type` field
- [ ] `conversations` and `journals` collections populated
- [ ] Vector search returns results via Atlas
- [ ] Bias reports in `reports/bias/` with visualization PNGs
- [ ] Schema reports in `reports/schema/` with pass/fail expectations
- [ ] BERTopic models saved to `models/bertopic_journals/`, `models/bertopic_conversations/`, and `models/bertopic_severity/`
- [ ] MLflow experiments tracked in `mlruns/`
- [ ] All 367 tests passing (`pytest tests/ -v`)

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
| `GCS_KEY_FILE` | No | Path to GCS service account JSON key (default: `./calm-ai-bucket-key.json`) |
| `MODEL_REGISTRY_BUCKET` | No | GCS bucket for model uploads (default: `calm-ai_model_registry`) |
| `MODEL_REGISTRY_PREFIX` | No | Path prefix in GCS bucket (default: `models/bertopic`) |
| `MODEL_MAX_OUTLIER_RATIO` | No | Max outlier ratio for promotion gate (default: `0.20`) |
| `MODEL_MIN_SILHOUETTE` | No | Min silhouette score for promotion (default: `0.10`) |
| `MODEL_MIN_TOPIC_DIVERSITY` | No | Min topic diversity for promotion (default: `0.50`) |
| `MODEL_MAX_BIAS_DISPARITY` | No | Max bias disparity delta for promotion (default: `0.10`) |
| `ENABLE_MODEL_SELECTION_GATE` | No | Enable selection policy gate (default: `true`) |
| `ENABLE_MODEL_PROMOTION` | No | Enable model promotion to GCS (default: `true`) |
| `ENABLE_MODEL_ROLLBACK` | No | Enable automatic rollback on smoke test failure (default: `true`) |
