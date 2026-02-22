# backend configuration
# loads env vars for mongodb, jwt, gemini, embedding model

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class Settings(BaseSettings):
    # mongodb
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "calm_ai_db")

    # jwt auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "calmai-dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # gemini (for rag answer generation)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # embedding model
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = 384

    # cors
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # incoming journal validation
    INCOMING_JOURNAL_MIN_LENGTH: int = 10
    INCOMING_JOURNAL_MAX_LENGTH: int = 10000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
