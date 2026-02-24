# vertex_embedding_client.py — langchain-compatible embeddings backed by a vertex ai endpoint
#
# authentication: uses google application default credentials (ADC).
# set GOOGLE_APPLICATION_CREDENTIALS env var to a service account key file, or
# run `gcloud auth application-default login` locally.
#
# expected endpoint request/response schema (standard vertex ai text embedding format):
#   POST {VERTEX_AI_ENDPOINT_URL}
#   body: {"instances": [{"content": "text"}, ...]}
#   response: {"predictions": [{"embeddings": {"values": [0.1, 0.2, ...]}}]}
#
# usage:
#   client = probe_vertex_ai_endpoint(endpoint_url)
#   if client:
#       embedding = client.embed_query("some text")
#   else:
#       # endpoint unreachable or misconfigured — fall back to huggingface

import logging
from typing import Optional

import httpx
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class VertexAIEmbeddingClient(Embeddings):
    """LangChain-compatible embedding client for Vertex AI online prediction endpoints.

    Implements the standard langchain Embeddings interface so it can be used
    as a drop-in replacement anywhere HuggingFaceEmbeddings is used.

    Authentication is handled via Google Application Default Credentials (ADC).
    Tokens are refreshed automatically on expiry.
    """

    def __init__(self, endpoint_url: str, batch_size: int = 32):
        """
        Args:
            endpoint_url: Full Vertex AI prediction endpoint URL, e.g.
                https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/
                locations/{LOCATION}/endpoints/{ENDPOINT_ID}:predict
            batch_size: Max instances per request (Vertex AI limits vary by endpoint).
        """
        self.endpoint_url = endpoint_url
        self.batch_size = batch_size
        self._credentials: Optional[object] = None

        # fail fast if google-auth is missing
        try:
            import google.auth  # noqa: F401
            import google.auth.transport.requests  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "google-auth is required for VertexAIEmbeddingClient. "
                "Add google-auth to requirements.txt and reinstall."
            ) from exc

    def _get_auth_token(self) -> str:
        """Return a valid Bearer token via Google Application Default Credentials."""
        import google.auth
        import google.auth.transport.requests

        if self._credentials is None:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

        # refresh() is idempotent when the token is still valid
        auth_request = google.auth.transport.requests.Request()
        self._credentials.refresh(auth_request)
        return self._credentials.token  # type: ignore[union-attr]

    def _call_endpoint(self, texts: list[str]) -> list[list[float]]:
        """POST a batch of texts to the endpoint and return embedding vectors."""
        token = self._get_auth_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"instances": [{"content": t} for t in texts]}

        response = httpx.post(
            self.endpoint_url,
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        predictions = data.get("predictions", [])

        embeddings: list[list[float]] = []
        for pred in predictions:
            values = pred.get("embeddings", {}).get("values")
            if values is None:
                raise ValueError(
                    f"Unexpected response schema from Vertex AI endpoint. "
                    f"Expected predictions[].embeddings.values but got keys: {list(pred.keys())}. "
                    f"Check that the deployed model uses the standard text-embedding response format."
                )
            embeddings.append(values)

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Vertex AI returned {len(embeddings)} predictions for {len(texts)} inputs."
            )

        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents in batches."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            all_embeddings.extend(self._call_endpoint(batch))
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        return self._call_endpoint([text])[0]


def probe_vertex_ai_endpoint(endpoint_url: str) -> Optional[VertexAIEmbeddingClient]:
    """Probe a Vertex AI embedding endpoint at startup before committing to it.

    Sends a short test sentence and validates that the response is a non-empty
    list of floats (i.e. a real embedding vector).

    Returns:
        A ready-to-use VertexAIEmbeddingClient if the probe succeeds.
        None if the endpoint is unreachable, misconfigured, or returns bad data —
        callers should fall back to HuggingFaceEmbeddings in that case.
    """
    try:
        client = VertexAIEmbeddingClient(endpoint_url)
        test_embedding = client.embed_query("startup embedding health check")

        if not isinstance(test_embedding, list) or len(test_embedding) == 0:
            logger.warning(
                "Vertex AI endpoint probe: response is not a non-empty list "
                f"(got type={type(test_embedding).__name__})"
            )
            return None

        # spot-check the first few values are numeric
        sample = test_embedding[:10]
        if not all(isinstance(v, (int, float)) for v in sample):
            logger.warning(
                "Vertex AI endpoint probe: embedding values are not numeric "
                f"(sample types: {[type(v).__name__ for v in sample]})"
            )
            return None

        logger.info(
            f"Vertex AI embedding endpoint probe succeeded "
            f"(dim={len(test_embedding)}, url={endpoint_url})"
        )
        return client

    except ImportError as exc:
        logger.warning(f"Vertex AI client unavailable — missing dependency: {exc}")
        return None
    except Exception as exc:
        logger.warning(
            f"Vertex AI endpoint probe failed — will fall back to HuggingFace: {exc}"
        )
        return None
