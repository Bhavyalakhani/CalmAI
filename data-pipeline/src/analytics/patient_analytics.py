# per-patient analytics for the therapist dashboard
# uses bertopic model inference for topic classification
# returns unclassified results when model is not available
# results are upserted into the patient_analytics collection

import logging
from typing import Dict, Any, List, Optional
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd


def _sanitize_for_mongo(obj: Any) -> Any:
    """recursively convert numpy/pandas types to native python types
    so pymongo can serialize them to bson."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_mongo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_mongo(item) for item in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Period):
        return str(obj)
    return obj

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class PatientAnalytics:

    def __init__(self):
        self.settings = config.settings
        self._inference = None
        self._model_loaded: Optional[bool] = None

    def _ensure_model(self) -> bool:
        """try to load the journal topic model (once). returns True if model is ready."""
        if self._model_loaded is not None:
            return self._model_loaded

        try:
            from topic_modeling.inference import TopicModelInference
            self._inference = TopicModelInference(model_type="journals")
            self._model_loaded = self._inference.load()
        except Exception as e:
            logger.warning(f"Could not load topic model: {e}")
            self._model_loaded = False

        if not self._model_loaded:
            logger.warning("Journal topic model not available — topics will be unclassified")

        return self._model_loaded

    # topic classification

    def classify_topics(self, text: str) -> Dict[str, Any]:
        """classify a journal entry using the trained bertopic model.
        returns dict with topic_id, label, keywords, probability.
        returns unclassified result if model unavailable."""
        if self._ensure_model():
            return self._inference.predict_single(text)
        return {
            "topic_id": -1,
            "label": "unclassified",
            "keywords": [],
            "probability": None,
        }

    def classify_topics_batch(self, docs: List[str]) -> List[Dict[str, Any]]:
        """classify multiple documents at once (more efficient than one-by-one).
        returns list of dicts with topic_id, label, keywords, probability.
        returns unclassified results if model unavailable."""
        if not docs:
            return []

        if self._ensure_model():
            return self._inference.classify_with_distribution(docs)
        return [
            {"topic_id": -1, "label": "unclassified", "keywords": [], "probability": None}
            for _ in docs
        ]

    # main analytics computation

    def compute_patient_analytics(self, journals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """compute analytics for a single patient from their journal entries.
        uses bertopic model when available, returns empty distributions otherwise.
        expects a list of journal dicts with 'content', 'entry_date', etc."""
        if not journals:
            return {
                "total_entries": 0,
                "topic_distribution": [],
                "topics_over_time": [],
                "representative_entries": [],
                "avg_word_count": 0,
                "entry_frequency": {},
                "date_range": None,
                "model_version": None,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }

        df = pd.DataFrame(journals)
        docs = df["content"].astype(str).tolist()

        # topic distribution via model
        if self._ensure_model():
            topics, probs = self._inference.predict(docs)
            topic_distribution = self._inference.get_topic_distribution(topics)
            topics_over_time = self._compute_topics_over_time(df, topics)
            representative_entries = self._find_representative_entries(df, topics, probs)
            model_version = "bertopic"
        else:
            topic_distribution = []
            topics_over_time = []
            representative_entries = []
            model_version = "unavailable"

        # word count stats (unchanged)
        word_counts = df["content"].astype(str).str.split().str.len()
        avg_word_count = round(float(word_counts.mean()), 1) if len(word_counts) > 0 else 0

        # entry frequency by month (unchanged)
        entry_frequency = {}
        if "entry_date" in df.columns:
            dates = pd.to_datetime(df["entry_date"], errors="coerce")
            valid_dates = dates.dropna()
            if len(valid_dates) > 0:
                monthly = valid_dates.dt.to_period("M").value_counts().sort_index()
                entry_frequency = {str(k): int(v) for k, v in monthly.items()}

        # date range (unchanged)
        date_range = None
        if "entry_date" in df.columns:
            dates = pd.to_datetime(df["entry_date"], errors="coerce").dropna()
            if len(dates) > 0:
                date_range = {
                    "first": dates.min().isoformat(),
                    "last": dates.max().isoformat(),
                    "span_days": int((dates.max() - dates.min()).days),
                }

        result = {
            "total_entries": len(journals),
            "topic_distribution": topic_distribution,
            "topics_over_time": topics_over_time,
            "representative_entries": representative_entries,
            "avg_word_count": avg_word_count,
            "entry_frequency": entry_frequency,
            "date_range": date_range,
            "model_version": model_version,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        # ensure all numpy/pandas types are native python for mongodb serialization
        return _sanitize_for_mongo(result)

    # bertopic-specific analytics helpers

    def _compute_topics_over_time(
        self, df: pd.DataFrame, topics: List[int],
    ) -> List[Dict[str, Any]]:
        """compute topic frequency by month for the patient"""
        if "entry_date" not in df.columns:
            return []

        df_work = df.copy()
        df_work["_topic_id"] = topics
        df_work["_month"] = pd.to_datetime(df_work["entry_date"], errors="coerce").dt.to_period("M")
        df_work = df_work.dropna(subset=["_month"])

        if df_work.empty:
            return []

        result = []
        grouped = df_work.groupby(["_month", "_topic_id"]).size().reset_index(name="frequency")

        for _, row in grouped.iterrows():
            topic_id = int(row["_topic_id"])
            if topic_id == -1:
                continue
            result.append({
                "month": str(row["_month"]),
                "topic_id": topic_id,
                "label": self._inference.get_topic_label(topic_id),
                "frequency": int(row["frequency"]),
            })

        return sorted(result, key=lambda x: (x["month"], -x["frequency"]))

    def _find_representative_entries(
        self,
        df: pd.DataFrame,
        topics: List[int],
        probs: Optional[np.ndarray],
    ) -> List[Dict[str, Any]]:
        """find the highest-probability entry for each topic"""
        if probs is None:
            return []

        df_work = df.copy()
        df_work["_topic_id"] = topics

        if len(probs.shape) > 1:
            df_work["_probability"] = np.max(probs, axis=1)
        else:
            df_work["_probability"] = probs

        # exclude outliers
        df_valid = df_work[df_work["_topic_id"] != -1]
        if df_valid.empty:
            return []

        result = []
        for topic_id, group in df_valid.groupby("_topic_id"):
            top = group.nlargest(1, "_probability").iloc[0]
            result.append({
                "topic_id": int(topic_id),
                "label": self._inference.get_topic_label(int(topic_id)),
                "journal_id": str(top.get("journal_id", "")),
                "content": str(top.get("content", ""))[:200],
                "entry_date": str(top.get("entry_date", "")),
                "probability": round(float(top["_probability"]), 3),
            })

        return sorted(result, key=lambda x: -x["probability"])
