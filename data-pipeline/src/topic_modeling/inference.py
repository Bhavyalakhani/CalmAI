# topic model inference
# loads saved bertopic models and predicts topics on new documents
# used by dag 2 (incoming journals) and backend for on-the-fly classification

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import get_models_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TopicModelInference:
    """loads a saved bertopic model and predicts topics on new documents"""

    def __init__(self, model_type: str = "journals"):
        self.model_type = model_type
        self.model = None
        self.embedding_model = None
        self._loaded = False

    def load(self, path: Optional[Path] = None) -> bool:
        """load a saved bertopic model from disk.

        args:
            path: path to model directory. defaults to models/bertopic_{type}/latest/model

        returns:
            True if loaded successfully, False otherwise
        """
        from bertopic import BERTopic

        model_dir = path or (get_models_dir(self.model_type) / "model")

        if not model_dir.exists():
            logger.warning(f"Model not found at {model_dir}")
            return False

        try:
            self.model = BERTopic.load(str(model_dir))
            self._loaded = True
            logger.info(f"Loaded {self.model_type} topic model from {model_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model from {model_dir}: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self.model is not None

    def predict(
        self,
        docs: List[str],
        embeddings: Optional[np.ndarray] = None,
    ) -> Tuple[List[int], Optional[np.ndarray]]:
        """predict topics for new documents.

        args:
            docs: list of text documents
            embeddings: pre-calculated embeddings (optional)

        returns:
            tuple of (topic_ids, probabilities)
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        topics, probs = self.model.transform(docs, embeddings)
        logger.info(f"Predicted topics for {len(docs)} documents")
        return topics, probs

    def predict_single(self, text: str) -> Dict[str, Any]:
        """predict topic for a single document with full metadata.

        args:
            text: input document text

        returns:
            dict with topic_id, label, keywords, probability
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        topics, probs = self.model.transform([text])
        topic_id = int(topics[0])

        result = {
            "topic_id": topic_id,
            "label": self.get_topic_label(topic_id),
            "keywords": self.get_topic_keywords(topic_id),
        }

        if probs is not None:
            if len(probs.shape) > 1:
                result["probability"] = float(np.max(probs[0]))
            else:
                result["probability"] = float(probs[0])

        return result

    def get_topic_label(self, topic_id: int) -> str:
        """get the best available label for a topic.
        prefers llm label > keybert label > default name.
        """
        if not self.is_loaded or topic_id == -1:
            return "Outlier"

        topic_info = self.model.get_topic_info()
        row = topic_info[topic_info["Topic"] == topic_id]

        if row.empty:
            return f"Topic {topic_id}"

        row = row.iloc[0]

        # prefer llm label if available
        if "llm" in row and row["llm"] is not None:
            label = self._extract_label(row["llm"])
            if label:
                return label

        # fallback to keybert
        if "keybert" in row and row["keybert"] is not None:
            label = self._extract_label(row["keybert"])
            if label:
                return label

        # fallback to default name
        return str(row.get("Name", f"Topic {topic_id}"))

    @staticmethod
    def _extract_label(raw) -> str:
        """extract a clean label string from a bertopic representation value.
        multi-aspect representations store values as lists (e.g.
        ['topic: Sleep Quality and Insomnia', '', '', ...]). single-aspect
        representations store plain strings. handles both, strips 'topic: '
        prefix added by the gemini prompt, and returns empty string if nothing useful.
        """
        if isinstance(raw, (list, tuple)):
            # take the first non-empty element
            for item in raw:
                text = str(item).strip() if item is not None else ""
                if text:
                    raw = text
                    break
            else:
                return ""

        text = str(raw).strip()
        if not text:
            return ""

        # strip "topic: " prefix added by gemini prompt format
        if text.lower().startswith("topic: "):
            text = text[7:].strip()
        elif text.lower().startswith("topic:"):
            text = text[6:].strip()

        return text

    def get_topic_keywords(self, topic_id: int, top_n: int = 10) -> List[str]:
        """get top keywords for a topic"""
        if not self.is_loaded or topic_id == -1:
            return []

        topic_words = self.model.get_topic(topic_id)
        if not topic_words:
            return []

        return [w for w, _ in topic_words[:top_n]]

    def get_all_topic_info(self) -> List[Dict[str, Any]]:
        """get info for all topics (excluding outlier topic -1)"""
        if not self.is_loaded:
            return []

        records = []
        topic_info = self.model.get_topic_info()

        for _, row in topic_info.iterrows():
            topic_id = int(row["Topic"])
            if topic_id == -1:
                continue

            record = {
                "topic_id": topic_id,
                "count": int(row["Count"]),
                "label": self.get_topic_label(topic_id),
                "keywords": self.get_topic_keywords(topic_id),
            }
            records.append(record)

        return records

    def get_topic_distribution(self, topics: List[int]) -> List[Dict[str, Any]]:
        """compute topic distribution from a list of predicted topic ids.

        args:
            topics: list of topic ids (from predict())

        returns:
            list of dicts with topic_id, label, count, percentage
        """
        from collections import Counter

        # filter outliers
        valid_topics = [t for t in topics if t != -1]
        total = len(valid_topics) if valid_topics else 1

        counts = Counter(valid_topics)
        distribution = []

        for topic_id, count in sorted(counts.items(), key=lambda x: -x[1]):
            topic_id = int(topic_id)
            distribution.append({
                "topic_id": topic_id,
                "label": self.get_topic_label(topic_id),
                "keywords": self.get_topic_keywords(topic_id, top_n=5),
                "count": int(count),
                "percentage": round(count / total * 100, 1),
            })

        return distribution

    def classify_with_distribution(
        self,
        docs: List[str],
        embeddings: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """classify documents and return per-document topic assignments with metadata.

        args:
            docs: list of text documents
            embeddings: pre-calculated embeddings (optional)

        returns:
            list of dicts, one per document, with topic_id, label, keywords, probability
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        topics, probs = self.model.transform(docs, embeddings)
        results = []

        for i, (topic_id, doc) in enumerate(zip(topics, docs)):
            topic_id = int(topic_id)
            result = {
                "topic_id": topic_id,
                "label": self.get_topic_label(topic_id),
                "keywords": self.get_topic_keywords(topic_id, top_n=5),
            }

            if probs is not None:
                if len(probs.shape) > 1:
                    result["probability"] = float(np.max(probs[i]))
                else:
                    result["probability"] = float(probs[i])

            results.append(result)

        return results

    # severity-specific methods (for model_type="severity")

    _SEVERITY_LEVELS = {"crisis", "severe", "moderate", "mild"}

    def _topic_to_severity(self, topic_id: int) -> str:
        """map a severity model topic_id to a canonical severity level.
        the gemini prompt labels each cluster as crisis/severe/moderate/mild.
        outlier topic (-1) maps to 'unknown'.
        """
        if topic_id == -1:
            return "unknown"
        label = self.get_topic_label(topic_id).lower().strip()
        for level in self._SEVERITY_LEVELS:
            if level in label:
                return level
        return "unknown"

    def predict_severity(
        self,
        docs: List[str],
        embeddings: Optional[np.ndarray] = None,
    ) -> List[str]:
        """predict severity levels for documents.
        requires a severity model (model_type='severity').

        args:
            docs: list of text documents
            embeddings: pre-calculated embeddings (optional)

        returns:
            list of severity strings (crisis/severe/moderate/mild/unknown)
        """
        topics, _ = self.predict(docs, embeddings)
        return [self._topic_to_severity(int(t)) for t in topics]

    def predict_severity_series(self, series: "pd.Series") -> "pd.Series":
        """predict severity for a pandas Series of text.
        returns a Series of severity labels."""
        texts = series.astype(str).tolist()
        results = self.predict_severity(texts)
        return pd.Series(results, index=series.index)
