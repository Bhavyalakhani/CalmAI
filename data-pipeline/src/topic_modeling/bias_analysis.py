# bertopic-based bias analysis
# replaces keyword-based slicing with model-discovered topic clusters
# analyzes topic distribution balance, underrepresentation, patient coverage,
# temporal patterns, response quality by topic, and generates visualizations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import get_reports_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TopicBiasAnalyzer:
    """analyzes bias in model-discovered topic distributions.
    works for both journal and conversation topic models.
    """

    UNDERREPRESENTATION_THRESHOLD = 3.0  # % below which a topic is flagged
    SPARSE_PATIENT_THRESHOLD = 10  # patients with fewer entries are flagged

    def __init__(self, model_type: str = "journals"):
        self.model_type = model_type
        self.settings = config.settings

    # journal bias analysis

    def analyze_journal_bias(
        self,
        df: pd.DataFrame,
        topics: List[int],
        topic_info: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """full bias analysis on journal data with bertopic-assigned topics.

        args:
            df: journal dataframe (must have patient_id, content, entry_date, word_count, etc.)
            topics: list of topic ids assigned to each row (from model.transform or model.topics_)
            topic_info: list of topic dicts from trainer._serialize_topic_info()

        returns:
            bias report dict
        """
        df = df.copy()
        df["topic_id"] = topics

        # build label lookup
        label_map = {t["topic_id"]: t.get("llm_label") or t.get("keybert_label") or t.get("name", f"Topic {t['topic_id']}") for t in topic_info}

        report = {
            "dataset_name": f"{self.model_type}_bias_report",
            "model_type": self.model_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df),
            "num_topics": len(topic_info),
        }

        # topic distribution
        report["topic_distribution"] = self._analyze_topic_distribution(df, label_map)

        # underrepresented topics
        report["underrepresented_topics"] = self._find_underrepresented(
            report["topic_distribution"]
        )

        # patient distribution
        if "patient_id" in df.columns:
            report["patient_distribution"] = self._analyze_patient_distribution(df)
            report["sparse_patients"] = self._find_sparse_patients(df)
            report["patient_topic_coverage"] = self._analyze_patient_topic_coverage(df, label_map)

        # temporal patterns
        report["temporal_patterns"] = self._analyze_temporal_patterns(df)

        # topic overlap (multi-label from probabilities not available here,
        # but we can check outlier distribution)
        report["outlier_analysis"] = self._analyze_outliers(df)

        # mitigation notes
        report["mitigation_notes"] = self._generate_mitigation_notes(report)

        return report

    # conversation bias analysis

    def analyze_conversation_bias(
        self,
        df: pd.DataFrame,
        topics: List[int],
        topic_info: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """full bias analysis on conversation data with bertopic-assigned topics.

        args:
            df: conversation dataframe (must have context, response, word counts, etc.)
            topics: list of topic ids assigned to each row
            topic_info: list of topic dicts

        returns:
            bias report dict
        """
        df = df.copy()
        df["topic_id"] = topics

        label_map = {t["topic_id"]: t.get("llm_label") or t.get("keybert_label") or t.get("name", f"Topic {t['topic_id']}") for t in topic_info}

        report = {
            "dataset_name": "conversation_bias_report",
            "model_type": "conversations",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df),
            "num_topics": len(topic_info),
        }

        # topic distribution
        report["topic_distribution"] = self._analyze_topic_distribution(df, label_map)

        # underrepresented topics
        report["underrepresented_topics"] = self._find_underrepresented(
            report["topic_distribution"]
        )

        # cross analysis: response length by topic
        if "response_word_count" in df.columns:
            report["cross_analysis"] = self._cross_analyze_response_length(df, label_map)

        # severity classification via bertopic severity model
        report["severity_distribution"] = self._analyze_severity(df)

        # topic overlap via multi-topic analysis
        report["outlier_analysis"] = self._analyze_outliers(df)

        # mitigation notes
        report["mitigation_notes"] = self._generate_mitigation_notes(report)

        return report

    # shared analysis methods

    def _analyze_topic_distribution(
        self,
        df: pd.DataFrame,
        label_map: Dict[int, str],
    ) -> Dict[str, Dict[str, Any]]:
        """distribution of documents across topics"""
        total = len(df)
        if total == 0:
            return {}

        topic_counts = df["topic_id"].value_counts()
        distribution = {}

        for topic_id, count in topic_counts.items():
            topic_id_int = int(topic_id)
            if topic_id_int == -1:
                label = "Outlier"
            else:
                label = str(label_map.get(topic_id_int, f"Topic {topic_id_int}"))

            stats = {
                "count": int(count),
                "percentage": round(count / total * 100, 2),
            }

            # word count stats per topic
            topic_df = df[df["topic_id"] == topic_id]
            if "word_count" in topic_df.columns and len(topic_df) > 0:
                stats["word_count_mean"] = round(float(topic_df["word_count"].mean()), 2)

            distribution[label] = stats

        return distribution

    def _find_underrepresented(
        self, distribution: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """find topics below the underrepresentation threshold"""
        return [
            topic
            for topic, stats in distribution.items()
            if topic != "Outlier"
            and stats["percentage"] < self.UNDERREPRESENTATION_THRESHOLD
        ]

    def _analyze_patient_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """patient-level entry distribution"""
        patient_counts = df.groupby("patient_id").size()
        return {
            "total_patients": int(len(patient_counts)),
            "entries_per_patient_mean": round(float(patient_counts.mean()), 2),
            "entries_per_patient_std": round(float(patient_counts.std()), 2),
            "entries_per_patient_min": int(patient_counts.min()),
            "entries_per_patient_max": int(patient_counts.max()),
            "entries_per_patient_median": float(patient_counts.median()),
        }

    def _find_sparse_patients(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """patients with fewer than threshold entries"""
        patient_counts = df.groupby("patient_id").size()
        sparse = patient_counts[patient_counts < self.SPARSE_PATIENT_THRESHOLD]
        return [
            {"patient_id": str(pid), "entry_count": int(count)}
            for pid, count in sparse.items()
        ]

    def _analyze_patient_topic_coverage(
        self,
        df: pd.DataFrame,
        label_map: Dict[int, str],
    ) -> Dict[str, Any]:
        """which topics each patient covers — flags patients stuck on one topic"""
        patient_topics = df.groupby("patient_id")["topic_id"].apply(set)
        all_topics = set(label_map.keys())

        coverage = {}
        single_topic_patients = []

        for pid, topics in patient_topics.items():
            topic_set = set(topics) if not isinstance(topics, set) else topics
            valid = topic_set - {-1}
            labeled = [str(label_map.get(t, f"Topic {t}")) for t in valid]
            coverage[str(pid)] = {
                "num_topics": len(valid),
                "topics": labeled,
                "coverage_ratio": round(len(valid) / len(all_topics), 2) if all_topics else 0,
            }
            if len(valid) <= 1:
                single_topic_patients.append(str(pid))

        topic_counts_per_patient = []
        for topics in patient_topics:
            topic_set = set(topics) if not isinstance(topics, set) else topics
            topic_counts_per_patient.append(len(topic_set - {-1}))

        return {
            "per_patient": coverage,
            "single_topic_patients": single_topic_patients,
            "avg_topics_per_patient": round(
                float(np.mean(topic_counts_per_patient)), 2
            ) if topic_counts_per_patient else 0,
        }

    def _analyze_temporal_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """entries by day/month and gap stats"""
        patterns = {}

        if "day_of_week" in df.columns:
            day_counts = df["day_of_week"].value_counts().sort_index()
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            patterns["entries_by_day"] = {
                day_names[int(k)]: int(v)
                for k, v in day_counts.items()
                if pd.notna(k) and int(k) < 7
            }

        if "month" in df.columns:
            month_counts = df["month"].value_counts().sort_index()
            patterns["entries_by_month"] = {
                int(k): int(v) for k, v in month_counts.items() if pd.notna(k)
            }

        if "days_since_last" in df.columns:
            valid_gaps = df["days_since_last"][df["days_since_last"] > 0]
            if len(valid_gaps) > 0:
                patterns["entry_gap_mean"] = round(float(valid_gaps.mean()), 2)
                patterns["entry_gap_median"] = float(valid_gaps.median())
                patterns["entry_gap_max"] = int(valid_gaps.max())

        return patterns

    def _cross_analyze_response_length(
        self,
        df: pd.DataFrame,
        label_map: Dict[int, str],
    ) -> Dict[str, Any]:
        """check if certain topics get shorter/longer responses"""
        overall_mean = float(df["response_word_count"].mean()) if len(df) > 0 else 0

        shorter = []
        longer = []

        for topic_id, label in label_map.items():
            topic_df = df[df["topic_id"] == topic_id]
            if len(topic_df) < 10:
                continue

            mean_len = float(topic_df["response_word_count"].mean())
            diff = mean_len - overall_mean

            entry = {
                "topic": str(label),
                "topic_id": topic_id,
                "response_mean": round(mean_len, 2),
                "diff_from_overall": round(diff, 2),
            }

            if diff < -20:
                shorter.append(entry)
            elif diff > 20:
                longer.append(entry)

        return {
            "overall_response_mean": round(overall_mean, 2),
            "shorter_response_topics": sorted(shorter, key=lambda x: x["diff_from_overall"]),
            "longer_response_topics": sorted(longer, key=lambda x: -x["diff_from_overall"]),
        }

    def _analyze_severity(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """bertopic-based severity classification.
        uses the trained severity model to cluster conversations by emotional intensity.
        """
        text_col = "context" if "context" in df.columns else "content"
        if text_col not in df.columns:
            return {}

        df = df.copy()

        try:
            from .inference import TopicModelInference
            severity_inference = TopicModelInference(model_type="severity")
            if severity_inference.load():
                texts = df[text_col].astype(str).tolist()
                df["severity"] = severity_inference.predict_severity(texts)
            else:
                df["severity"] = "unknown"
        except Exception:
            df["severity"] = "unknown"

        from src.severity import SEVERITY_LEVELS
        total = len(df)
        distribution = {}
        for level in SEVERITY_LEVELS:
            count = int((df["severity"] == level).sum())
            distribution[level] = {
                "count": count,
                "percentage": round(count / total * 100, 2) if total > 0 else 0,
            }

        return distribution

    def _analyze_outliers(self, df: pd.DataFrame) -> Dict[str, Any]:
        """outlier topic (-1) analysis"""
        total = len(df)
        outlier_count = int((df["topic_id"] == -1).sum())

        return {
            "outlier_count": outlier_count,
            "outlier_percentage": round(outlier_count / total * 100, 2) if total > 0 else 0,
        }

    def _generate_mitigation_notes(self, report: Dict[str, Any]) -> List[str]:
        """generate actionable mitigation notes based on findings"""
        notes = []

        # underrepresented topics
        underrep = report.get("underrepresented_topics", [])
        if underrep:
            notes.append(
                f"[REPRESENTATION BIAS] {len(underrep)} underrepresented topic(s): "
                f"{', '.join(underrep)}. Consider collecting more data in these areas."
            )

        # sparse patients
        sparse = report.get("sparse_patients", [])
        if sparse:
            notes.append(
                f"[SAMPLING BIAS] {len(sparse)} patient(s) with fewer than "
                f"{self.SPARSE_PATIENT_THRESHOLD} entries. Their topic assignments "
                f"may be less reliable."
            )

        # single-topic patients
        coverage = report.get("patient_topic_coverage", {})
        single = coverage.get("single_topic_patients", [])
        if single:
            notes.append(
                f"[COVERAGE BIAS] {len(single)} patient(s) assigned to only 1 topic. "
                f"May indicate limited journaling range or model clustering artifact."
            )

        # high outlier ratio
        outlier_info = report.get("outlier_analysis", {})
        outlier_pct = outlier_info.get("outlier_percentage", 0)
        if outlier_pct > 15:
            notes.append(
                f"[MODEL QUALITY] {outlier_pct:.1f}% documents are outliers (topic -1). "
                f"Consider adjusting HDBSCAN min_cluster_size or running outlier reduction."
            )

        # response length disparity (conversations only)
        cross = report.get("cross_analysis", {})
        shorter = cross.get("shorter_response_topics", [])
        if shorter:
            topics_str = ", ".join(t["topic"] for t in shorter)
            notes.append(
                f"[RESPONSE BIAS] Topics receiving significantly shorter responses: "
                f"{topics_str}. Investigate counselor engagement for these topics."
            )

        if not notes:
            notes.append("No significant bias detected in data distribution.")

        return notes

    # visualizations

    def generate_visualizations(
        self,
        report: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> List[Path]:
        """generate bias analysis charts and save as png"""
        save_dir = output_dir or (self.settings.REPORTS_DIR / "bias")
        save_dir.mkdir(parents=True, exist_ok=True)
        saved_files = []

        # topic distribution bar chart
        try:
            path = self._plot_topic_distribution(report, save_dir)
            if path:
                saved_files.append(path)
        except Exception as e:
            logger.warning(f"Failed to generate topic distribution chart: {e}")

        # severity pie chart (conversations only)
        if "severity_distribution" in report:
            try:
                path = self._plot_severity_distribution(report, save_dir)
                if path:
                    saved_files.append(path)
            except Exception as e:
                logger.warning(f"Failed to generate severity chart: {e}")

        # entries by day (journals only)
        if "temporal_patterns" in report and "entries_by_day" in report.get("temporal_patterns", {}):
            try:
                path = self._plot_entries_by_day(report, save_dir)
                if path:
                    saved_files.append(path)
            except Exception as e:
                logger.warning(f"Failed to generate entries by day chart: {e}")

        # entries by month
        if "temporal_patterns" in report and "entries_by_month" in report.get("temporal_patterns", {}):
            try:
                path = self._plot_entries_by_month(report, save_dir)
                if path:
                    saved_files.append(path)
            except Exception as e:
                logger.warning(f"Failed to generate entries by month chart: {e}")

        logger.info(f"Generated {len(saved_files)} visualization(s)")
        return saved_files

    def _plot_topic_distribution(self, report: Dict, save_dir: Path) -> Optional[Path]:
        dist = report.get("topic_distribution", {})
        if not dist:
            return None

        # filter out outlier for cleaner chart
        filtered = {k: v for k, v in dist.items() if k != "Outlier"}
        if not filtered:
            return None

        labels = list(filtered.keys())
        counts = [v["count"] for v in filtered.values()]

        # truncate long labels
        labels = [l[:30] + "..." if len(l) > 30 else l for l in labels]

        fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.4)))
        bars = ax.barh(labels, counts, color="#4a9eff")
        ax.set_xlabel("Number of Documents")
        ax.set_title(f"{self.model_type.title()} Topic Distribution (BERTopic)")
        ax.invert_yaxis()
        plt.tight_layout()

        prefix = "journal" if self.model_type == "journals" else "conversation"
        path = save_dir / f"{prefix}_topic_distribution.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_severity_distribution(self, report: Dict, save_dir: Path) -> Optional[Path]:
        dist = report.get("severity_distribution", {})
        if not dist:
            return None

        labels = list(dist.keys())
        counts = [v["count"] for v in dist.values()]

        fig, ax = plt.subplots(figsize=(8, 8))
        colors = ["#ff4444", "#ff8844", "#ffcc44", "#44cc44", "#888888"]
        ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=colors[:len(labels)])
        ax.set_title("Conversation Severity Distribution")
        plt.tight_layout()

        path = save_dir / "severity_distribution.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_entries_by_day(self, report: Dict, save_dir: Path) -> Optional[Path]:
        entries_by_day = report.get("temporal_patterns", {}).get("entries_by_day", {})
        if not entries_by_day:
            return None

        days = list(entries_by_day.keys())
        counts = list(entries_by_day.values())

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(days, counts, color="#4a9eff")
        ax.set_ylabel("Number of Entries")
        ax.set_title("Journal Entries by Day of Week")
        plt.xticks(rotation=45)
        plt.tight_layout()

        path = save_dir / "journal_entries_by_day.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_entries_by_month(self, report: Dict, save_dir: Path) -> Optional[Path]:
        entries_by_month = report.get("temporal_patterns", {}).get("entries_by_month", {})
        if not entries_by_month:
            return None

        months = [str(k) for k in entries_by_month.keys()]
        counts = list(entries_by_month.values())

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(months, counts, color="#4a9eff")
        ax.set_xlabel("Month")
        ax.set_ylabel("Number of Entries")
        ax.set_title("Journal Entries by Month")
        plt.tight_layout()

        path = save_dir / "journal_entries_by_month.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def save_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> Path:
        """save bias report as json"""
        save_dir = self.settings.REPORTS_DIR / "bias"
        save_dir.mkdir(parents=True, exist_ok=True)

        prefix = "journal" if self.model_type == "journals" else "conversation"
        fname = filename or f"{prefix}_bias_report.json"
        path = save_dir / fname

        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Bias report saved to {path}")
        return path
