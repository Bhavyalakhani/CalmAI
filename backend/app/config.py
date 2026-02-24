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

    # embedding model (huggingface fallback)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = 384

    # vertex ai embedding endpoint (optional)
    # if set, the app will probe this endpoint at startup and use it for embeddings.
    # falls back to EMBEDDING_MODEL (huggingface) if the probe fails or this is empty.
    # full endpoint url: https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/
    #                    locations/{LOCATION}/endpoints/{ENDPOINT_ID}:predict
    # auth: google application default credentials (ADC) — set GOOGLE_APPLICATION_CREDENTIALS
    VERTEX_AI_ENDPOINT_URL: str = os.getenv("VERTEX_AI_ENDPOINT_URL", "")

    # cors
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # incoming journal validation
    INCOMING_JOURNAL_MIN_LENGTH: int = 10
    INCOMING_JOURNAL_MAX_LENGTH: int = 10000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
