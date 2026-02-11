"""
Central Config
"""
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    RAW_DATA_DIR: Path = PROJECT_ROOT / "data" / "raw"
    PROCESSED_DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"
    CONFIGS_DIR: Path = PROJECT_ROOT / "configs"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "calm_ai")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDINGS_DIR: Path = PROJECT_ROOT / "data" / "embeddings"
    
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