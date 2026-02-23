# severity classification for mental health conversations
# uses bertopic severity model — clusters conversations by emotional intensity
# single source of truth — imported by mongodb_client, conversation_bias, topic bias_analysis
#
# the severity bertopic model is trained on conversation data with a prompt
# that labels each cluster as crisis/severe/moderate/mild.
# falls back to "unknown" when model is not available.

import logging
import pandas as pd

from typing import List

logger = logging.getLogger(__name__)

# canonical severity levels (referenced by bias analysis / frontend / backend)
SEVERITY_LEVELS = ["crisis", "severe", "moderate", "mild", "unknown"]

# singleton inference model — lazy loaded once
_inference = None
_load_attempted = False


def _ensure_model() -> bool:
    """lazy-load the severity bertopic model (once)."""
    global _inference, _load_attempted
    if _load_attempted:
        return _inference is not None
    _load_attempted = True
    try:
        from topic_modeling.inference import TopicModelInference
        _inference = TopicModelInference(model_type="severity")
        if not _inference.load():
            logger.warning("Severity BERTopic model not found — classify_severity will return 'unknown'")
            _inference = None
    except Exception as e:
        logger.warning(f"Could not load severity model: {e}")
        _inference = None
    return _inference is not None


def reset_model():
    """reset the singleton (for testing)."""
    global _inference, _load_attempted
    _inference = None
    _load_attempted = False


def classify_severity(text: str) -> str:
    """classify severity of a single text using the bertopic severity model.
    returns one of: crisis, severe, moderate, mild, unknown."""
    if not text or not text.strip():
        return "unknown"
    if not _ensure_model():
        return "unknown"
    results = _inference.predict_severity([text])
    return results[0]


def classify_severity_batch(texts: List[str]) -> List[str]:
    """classify severity for a list of texts (batch — much faster than per-text).
    returns list of severity strings."""
    if not texts:
        return []
    if not _ensure_model():
        return ["unknown"] * len(texts)
    return _inference.predict_severity(texts)


def classify_severity_series(series: "pd.Series") -> "pd.Series":
    """classify severity for a pandas Series of text.
    returns a Series of severity labels."""
    if not _ensure_model():
        return pd.Series("unknown", index=series.index)
    return _inference.predict_severity_series(series)

