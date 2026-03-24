# unified embedding client — routes to a remote endpoint or local SentenceTransformer
# remote mode: sends texts over HTTP to a Vertex AI Online Prediction Endpoint
# local mode: loads SentenceTransformer on CPU (default for dev)

import logging
import time
from typing import List, Optional

import numpy as np

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """unified embedding interface — local model or remote endpoint.

    when USE_EMBEDDING_SERVICE is true, all embed() calls go to the remote
    endpoint via HTTP POST. otherwise, loads a local SentenceTransformer.
    """

    def __init__(self, model_name: Optional[str] = None, batch_size: int = 64):
        self.settings = config.settings
        # use getattr with defaults so mocked settings (MagicMock) don't accidentally
        # enable the remote endpoint — MagicMock attrs are truthy
        self.use_service = getattr(self.settings, 'USE_EMBEDDING_SERVICE', False) is True
        self.endpoint_url = getattr(self.settings, 'EMBEDDING_SERVICE_URL', '') or ''
        self.model_name = model_name or getattr(self.settings, 'EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        self.batch_size = batch_size
        self._local_model = None
        self._embedding_dim = None

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is not None:
            return self._embedding_dim
        if self.use_service:
            self._embedding_dim = self.settings.EMBEDDING_DIM
        else:
            self._ensure_local_model()
            self._embedding_dim = self._local_model.get_sentence_embedding_dimension()
        return self._embedding_dim

    def embed(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """embed a list of texts, returning shape (len(texts), embedding_dim)."""
        if not texts:
            return np.array([]).reshape(0, self.embedding_dim)

        if self.use_service:
            return self._call_endpoint(texts, show_progress)
        return self._embed_local(texts, show_progress)

    def _ensure_local_model(self):
        if self._local_model is not None:
            return
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading local embedding model: {self.model_name}")
        start = time.time()
        self._local_model = SentenceTransformer(self.model_name)
        self._embedding_dim = self._local_model.get_sentence_embedding_dimension()
        elapsed = time.time() - start
        logger.info(f"Model loaded in {elapsed:.2f}s | dim={self._embedding_dim}")

    def _embed_local(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """encode using local SentenceTransformer, batched with pre-allocated output."""
        self._ensure_local_model()

        total = len(texts)
        num_batches = (total + self.batch_size - 1) // self.batch_size
        result = np.empty((total, self.embedding_dim), dtype=np.float32)
        start = time.time()

        for i in range(0, total, self.batch_size):
            batch = texts[i : i + self.batch_size]  # noqa: E203
            batch_num = (i // self.batch_size) + 1

            batch_embeddings = self._local_model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
            result[i : i + len(batch)] = batch_embeddings  # noqa: E203

            if show_progress and (batch_num % 10 == 0 or batch_num == num_batches):
                elapsed = time.time() - start
                rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Local embed {batch_num}/{num_batches} | "
                    f"{i + len(batch)}/{total} texts | {rate:.0f} texts/sec"
                )

        total_time = time.time() - start
        logger.info(f"Local embedding complete: {total} texts in {total_time:.2f}s")
        return result

    @property
    def _is_vertex_ai(self) -> bool:
        """detect if the endpoint URL is a Vertex AI endpoint resource name."""
        return (
            "aiplatform.googleapis.com" in self.endpoint_url
            or self.endpoint_url.startswith("projects/")
        )

    def _call_endpoint(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """send texts to the remote embedding endpoint in batches."""
        if not self.endpoint_url:
            raise ValueError(
                "USE_EMBEDDING_SERVICE is true but EMBEDDING_SERVICE_URL is not set"
            )

        if self._is_vertex_ai:
            return self._call_vertex_ai(texts, show_progress)
        return self._call_http(texts, show_progress)

    def _call_http(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """send texts to a plain HTTP endpoint (e.g. Cloud Run)."""
        import requests

        total = len(texts)
        num_batches = (total + self.batch_size - 1) // self.batch_size
        result = np.empty((total, self.embedding_dim), dtype=np.float32)
        start = time.time()
        url = self.endpoint_url.rstrip("/") + "/embed"

        for i in range(0, total, self.batch_size):
            batch = texts[i : i + self.batch_size]  # noqa: E203
            batch_num = (i // self.batch_size) + 1

            response = requests.post(
                url,
                json={"texts": batch},
                timeout=120,
            )
            response.raise_for_status()
            embeddings = np.array(response.json()["embeddings"], dtype=np.float32)
            result[i : i + len(batch)] = embeddings  # noqa: E203

            if show_progress and (batch_num % 10 == 0 or batch_num == num_batches):
                elapsed = time.time() - start
                rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Remote embed {batch_num}/{num_batches} | "
                    f"{i + len(batch)}/{total} texts | {rate:.0f} texts/sec"
                )

        total_time = time.time() - start
        logger.info(f"Remote embedding complete: {total} texts in {total_time:.2f}s")
        return result

    def _call_vertex_ai(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """send texts to a Vertex AI Online Prediction Endpoint via the SDK.
        uses raw_predict which passes the request body as-is to the container
        at the predict route (/embed). auth is handled automatically via
        GOOGLE_APPLICATION_CREDENTIALS or the default service account.
        """
        import json
        from google.cloud import aiplatform

        # accept either a full resource name or an API URL
        endpoint_name = self.endpoint_url
        if "aiplatform.googleapis.com" in endpoint_name:
            # extract resource name from URL like:
            # https://REGION-aiplatform.googleapis.com/v1/projects/.../endpoints/ENDPOINT_ID
            parts = endpoint_name.split("/v1/")[-1] if "/v1/" in endpoint_name else endpoint_name
            endpoint_name = parts

        endpoint = aiplatform.Endpoint(endpoint_name=endpoint_name)

        total = len(texts)
        num_batches = (total + self.batch_size - 1) // self.batch_size
        result = np.empty((total, self.embedding_dim), dtype=np.float32)
        start = time.time()

        for i in range(0, total, self.batch_size):
            batch = texts[i : i + self.batch_size]  # noqa: E203
            batch_num = (i // self.batch_size) + 1

            response = endpoint.raw_predict(
                body=json.dumps({"texts": batch}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            data = json.loads(response.text)
            embeddings = np.array(data["embeddings"], dtype=np.float32)
            result[i : i + len(batch)] = embeddings  # noqa: E203

            if show_progress and (batch_num % 10 == 0 or batch_num == num_batches):
                elapsed = time.time() - start
                rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Vertex AI embed {batch_num}/{num_batches} | "
                    f"{i + len(batch)}/{total} texts | {rate:.0f} texts/sec"
                )

        total_time = time.time() - start
        logger.info(f"Vertex AI embedding complete: {total} texts in {total_time:.2f}s")
        return result
