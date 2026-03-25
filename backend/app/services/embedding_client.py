# langchain-compatible embedding client for the CalmAI backend
# routes to a remote endpoint (prod) or local HuggingFaceEmbeddings (dev)

import logging
from typing import List

from langchain_core.embeddings import Embeddings
from app.config import settings

logger = logging.getLogger(__name__)


class CalmAIEmbeddings(Embeddings):
    """langchain-compatible embedding interface that routes to either a remote
    Vertex AI endpoint or a local HuggingFaceEmbeddings model.

    when USE_EMBEDDING_SERVICE is true, sends texts to the remote endpoint.
    otherwise, falls back to the local SentenceTransformer model.
    """

    def __init__(self):
        self.use_service = settings.USE_EMBEDDING_SERVICE
        self.endpoint_url = settings.EMBEDDING_SERVICE_URL
        self._local_model = None

    def _ensure_local_model(self):
        if self._local_model is not None:
            return
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info(f"Loading local embedding model: {settings.EMBEDDING_MODEL}")
        self._local_model = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Local embedding model loaded")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self.use_service:
            return self._call_endpoint(texts)
        self._ensure_local_model()
        return self._local_model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def _call_endpoint(self, texts: List[str]) -> List[List[float]]:
        import requests

        if not self.endpoint_url:
            raise ValueError(
                "USE_EMBEDDING_SERVICE is true but EMBEDDING_SERVICE_URL is not set"
            )

        # detect Vertex AI endpoint vs plain HTTP
        if "aiplatform.googleapis.com" in self.endpoint_url or self.endpoint_url.startswith("projects/"):
            return self._call_vertex_ai(texts)

        url = self.endpoint_url.rstrip("/") + "/embed"
        response = requests.post(
            url,
            json={"texts": texts},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    def _call_vertex_ai(self, texts: List[str]) -> List[List[float]]:
        """call Vertex AI endpoint using raw HTTP with google-auth token."""
        import json
        import requests
        import google.auth
        import google.auth.transport.requests

        credentials, project = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        # build the rawPredict URL
        endpoint_name = self.endpoint_url
        if "aiplatform.googleapis.com" in endpoint_name:
            url = endpoint_name.rstrip("/") + ":rawPredict"
        else:
            # resource name like projects/.../endpoints/ENDPOINT_ID
            region = endpoint_name.split("/locations/")[1].split("/")[0] if "/locations/" in endpoint_name else "us-central1"
            url = f"https://{region}-aiplatform.googleapis.com/v1/{endpoint_name}:rawPredict"

        response = requests.post(
            url,
            json={"texts": texts},
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embeddings"]
