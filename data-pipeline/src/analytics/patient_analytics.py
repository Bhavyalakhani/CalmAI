# per-patient analytics for the therapist dashboard
# this is just a placeholder for now, we compute analytics with berttopic later.
# computes topic distribution, mood trends, entry frequency, theme classification
# results are upserted into the patient_analytics collection

import logging
from typing import Dict, Any, List
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# theme keywords (same as journal bias analyzer)
THEME_KEYWORDS = {
    "anxiety": ["anxious", "anxiety", "worry", "worried", "nervous", "panic", "fear", "stressed", "overwhelmed", "restless"],
    "depression": ["depressed", "depression", "sad", "hopeless", "empty", "numb", "worthless", "tired", "exhausted", "crying"],
    "positive": ["happy", "grateful", "thankful", "proud", "accomplished", "hopeful", "calm", "peaceful", "better", "progress"],
    "negative": ["angry", "frustrated", "upset", "annoyed", "irritated", "resentful", "bitter", "hurt", "lonely", "isolated"],
    "therapy": ["therapy", "therapist", "session", "counselor", "treatment", "coping", "technique", "exercise", "homework", "progress"],
    "sleep": ["sleep", "insomnia", "nightmare", "dream", "restless", "tired", "fatigue", "awake", "bedtime", "nap"],
    "social": ["friend", "family", "relationship", "social", "people", "conversation", "support", "group", "partner", "colleague"],
    "work": ["work", "job", "career", "boss", "coworker", "deadline", "project", "office", "meeting", "performance"],
}


class PatientAnalytics:

    def __init__(self):
        self.settings = config.settings

    def classify_themes(self, text: str) -> List[str]:
        """classify a journal entry into themes based on keyword matching"""
        text_lower = text.lower()
        matched = []
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                matched.append(theme)
        return matched if matched else ["unclassified"]

    def compute_patient_analytics(self, journals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """compute analytics for a single patient from their journal entries.
        expects a list of journal dicts with 'content', 'entry_date', etc."""
        if not journals:
            return {
                "total_entries": 0,
                "theme_distribution": {},
                "avg_word_count": 0,
                "entry_frequency": {},
                "date_range": None,
            }

        df = pd.DataFrame(journals)

        # theme distribution
        all_themes = []
        for content in df.get("content", pd.Series(dtype=str)):
            all_themes.extend(self.classify_themes(str(content)))
        theme_counts = dict(Counter(all_themes))
        total_themes = sum(theme_counts.values())
        theme_distribution = {
            k: round(v / total_themes * 100, 1)
            for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])
        }

        # word count stats
        word_counts = df["content"].astype(str).str.split().str.len()
        avg_word_count = round(float(word_counts.mean()), 1) if len(word_counts) > 0 else 0

        # entry frequency by month
        entry_frequency = {}
        if "entry_date" in df.columns:
            dates = pd.to_datetime(df["entry_date"], errors="coerce")
            valid_dates = dates.dropna()
            if len(valid_dates) > 0:
                monthly = valid_dates.dt.to_period("M").value_counts().sort_index()
                entry_frequency = {str(k): int(v) for k, v in monthly.items()}

        # date range
        date_range = None
        if "entry_date" in df.columns:
            dates = pd.to_datetime(df["entry_date"], errors="coerce").dropna()
            if len(dates) > 0:
                date_range = {
                    "first": dates.min().isoformat(),
                    "last": dates.max().isoformat(),
                    "span_days": int((dates.max() - dates.min()).days),
                }

        return {
            "total_entries": len(journals),
            "theme_distribution": theme_distribution,
            "avg_word_count": avg_word_count,
            "entry_frequency": entry_frequency,
            "date_range": date_range,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
