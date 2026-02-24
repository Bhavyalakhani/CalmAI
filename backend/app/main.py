# calmai backend api
# fastapi app with async mongodb, jwt auth, and langchain rag

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.db import db
from app.routers import auth, patients, journals, conversations, analytics, dashboard, search, prompts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """startup: connect to mongodb. shutdown: close connection."""
    logger.info("Starting CalmAI backend...")
    await db.connect()
    logger.info("CalmAI backend ready")
    yield
    logger.info("Shutting down CalmAI backend...")
    await db.close()


app = FastAPI(
    title="CalmAI API",
    description="Backend API for the CalmAI therapist platform — RAG search, patient management, journal submission",
    version="0.1.0",
    lifespan=lifespan,
)

# cors — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# register routers
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(journals.router)
app.include_router(conversations.router)
app.include_router(analytics.router)
app.include_router(dashboard.router)
app.include_router(search.router)
app.include_router(prompts.router)


@app.get("/health")
async def health_check():
    """basic health check endpoint"""
    return {"status": "ok", "service": "calmai-api"}
