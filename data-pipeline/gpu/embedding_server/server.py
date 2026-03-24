# embedding server — serves a SentenceTransformer model via REST API
# deployed on Vertex AI Online Prediction Endpoint with L4 GPU
# accepts POST /embed with {"texts": [...]}, returns {"embeddings": [[...], ...]}

import logging
import os
import time

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

app = FastAPI(title="CalmAI Embedding Server")

# global model — loaded once at startup
model: SentenceTransformer = None
embedding_dim: int = 0


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]


class InfoResponse(BaseModel):
    model_name: str
    embedding_dim: int
    device: str


@app.on_event("startup")
def load_model():
    global model, embedding_dim
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # load from HF cache (offline, no network calls) in fp16 to fit L4 24GB
    logger.info(f"Loading model '{MODEL_NAME}' on {device} in fp16...")
    t0 = time.time()
    model = SentenceTransformer(
        MODEL_NAME,
        device=device,
        model_kwargs={
            "torch_dtype": torch.float16,
            "low_cpu_mem_usage": True,
        },
    )
    embedding_dim = model.get_sentence_embedding_dimension()
    elapsed = time.time() - t0
    logger.info(f"Model loaded in {elapsed:.1f}s — dim={embedding_dim}, device={device}")


@app.get("/health")
def health():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy"}


@app.get("/info", response_model=InfoResponse)
def info():
    if model is None:
        raise HTTPException(status_code=503, detail="Model still loading")
    return InfoResponse(
        model_name=MODEL_NAME,
        embedding_dim=embedding_dim,
        device=str(model.device),
    )


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model still loading")
    if not request.texts:
        return EmbedResponse(embeddings=[])

    t0 = time.time()
    embeddings = model.encode(
        request.texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    elapsed = time.time() - t0
    logger.info(f"Embedded {len(request.texts)} texts in {elapsed:.2f}s")

    return EmbedResponse(embeddings=embeddings.tolist())


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
