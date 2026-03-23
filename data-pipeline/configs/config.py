# central configuration for the data pipeline
# loads env vars and provides paths used everywhere

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    RAW_DATA_DIR: Path = PROJECT_ROOT / "data" / "raw"
    PROCESSED_DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"
    CONFIGS_DIR: Path = PROJECT_ROOT / "configs"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    EMBEDDINGS_DIR: Path = PROJECT_ROOT / "data" / "embeddings"
    MODELS_DIR: Path = PROJECT_ROOT / "models"

    # external services
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "calm_ai")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # incoming journal validation thresholds
    INCOMING_JOURNAL_MIN_LENGTH: int = 10
    INCOMING_JOURNAL_MAX_LENGTH: int = 10000
    INCOMING_JOURNAL_BATCH_INTERVAL: str = "0 */12 * * *"

    # conditional retrain thresholds (dag 2)
    RETRAIN_ENTRY_THRESHOLD: int = 50
    RETRAIN_MAX_DAYS: int = 7

    # data drift detection thresholds (dag 2)
    # drift is checked when volume/time thresholds are NOT met
    # retraining triggers if ANY drift signal exceeds its threshold
    DRIFT_VOCAB_THRESHOLD: float = float(os.getenv("DRIFT_VOCAB_THRESHOLD", "0.65"))
    DRIFT_EMBEDDING_THRESHOLD: float = float(os.getenv("DRIFT_EMBEDDING_THRESHOLD", "0.30"))
    DRIFT_TOPIC_THRESHOLD: float = float(os.getenv("DRIFT_TOPIC_THRESHOLD", "0.25"))
    ENABLE_DRIFT_DETECTION: bool = os.getenv("ENABLE_DRIFT_DETECTION", "true").lower() == "true"

    # model lifecycle — promotion gates
    MODEL_MAX_OUTLIER_RATIO: float = float(os.getenv("MODEL_MAX_OUTLIER_RATIO", "0.20"))
    MODEL_MIN_SILHOUETTE: float = float(os.getenv("MODEL_MIN_SILHOUETTE", "0.10"))
    MODEL_MIN_TOPIC_DIVERSITY: float = float(os.getenv("MODEL_MIN_TOPIC_DIVERSITY", "0.50"))
    MODEL_MAX_BIAS_DISPARITY: float = float(os.getenv("MODEL_MAX_BIAS_DISPARITY", "0.10"))
    MODEL_PROMOTION_MIN_SCORE_DELTA: float = float(os.getenv("MODEL_PROMOTION_MIN_SCORE_DELTA", "0.01"))

    # model lifecycle — mlflow registry
    # defaults to local sqlite so the registry is enabled in dev/docker without extra config
    # override with a remote URI (e.g. postgresql://... or http://mlflow-server:5000) in production
    MLFLOW_TRACKING_URI: str = os.getenv(
        "MLFLOW_TRACKING_URI",
        f"sqlite:///{Path(__file__).parent.parent / 'mlruns' / 'mlflow.db'}",
    )
    MLFLOW_ARTIFACT_ROOT: str = os.getenv(
        "MLFLOW_ARTIFACT_ROOT",
        str(Path(__file__).parent.parent / "mlruns" / "artifacts"),
    )

    # model lifecycle — artifact registry bucket (placeholder)
    MODEL_REGISTRY_BUCKET: str = os.getenv("MODEL_REGISTRY_BUCKET", "")
    MODEL_REGISTRY_PREFIX: str = os.getenv("MODEL_REGISTRY_PREFIX", "models/bertopic")

    # GCS service account key file path
    # local dev: set GCS_KEY_FILE=./calm-ai-dvc-key.json in .env
    # docker: mounted read-only at /run/secrets/gcs-key.json via docker-compose
    GCS_KEY_FILE: str = os.getenv("GCS_KEY_FILE", "./calm-ai-bucket-key.json")

    # Vertex AI Model Registry
    # set GCP_PROJECT_ID to enable Vertex AI for model versioning
    # requires google-cloud-aiplatform and GCP credentials (ADC or GCS_KEY_FILE)
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")

    # model lifecycle — feature flags
    ENABLE_MODEL_SELECTION_GATE: bool = os.getenv("ENABLE_MODEL_SELECTION_GATE", "true").lower() == "true"
    ENABLE_MODEL_PROMOTION: bool = os.getenv("ENABLE_MODEL_PROMOTION", "true").lower() == "true"
    ENABLE_MODEL_ROLLBACK: bool = os.getenv("ENABLE_MODEL_ROLLBACK", "true").lower() == "true"

    def ensure_directories(self):
        dirs = [
            self.RAW_DATA_DIR / "conversations",
            self.RAW_DATA_DIR / "journals",
            self.PROCESSED_DATA_DIR / "conversations",
            self.PROCESSED_DATA_DIR / "journals",
            self.REPORTS_DIR / "validation",
            self.REPORTS_DIR / "bias",
            self.EMBEDDINGS_DIR / "incoming_journals",
            self.LOGS_DIR,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()