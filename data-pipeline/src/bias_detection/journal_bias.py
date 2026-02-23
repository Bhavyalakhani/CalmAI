# bias analysis for the journals dataset
# uses bertopic model inference for topic-based bias analysis
# model is required — trained in dag 1 before bias tasks run
# analyzes patient distribution, sparse patients, temporal patterns,
# topic distribution, and generates visualizations + mitigation notes

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

from .slicer import DataSlicer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class JournalBiasReport:
    dataset_name: str
    timestamp: str
    total_records: int
    total_patients: int
    model_version: str
    patient_distribution: Dict[str, Any]
    temporal_patterns: Dict[str, Any]
    topic_distribution: Dict[str, Dict[str, Any]]
    outlier_analysis: Dict[str, Any]
    sparse_patients: List[Dict[str, Any]]
    patient_topic_coverage: Dict[str, Any]
    mitigation_notes: List[str]


class JournalBiasAnalyzer:

    # patients with fewer entries than this are flagged
    SPARSE_THRESHOLD = 10

    def __init__(self):
        self.settings = config.settings
        self.df = None
        self.slicer = None
        self._inference = None
        self._model_loaded: Optional[bool] = None
        self._topic_info: List[Dict[str, Any]] = []
        self._model_version = "not_loaded"

    def _ensure_model(self) -> bool:
        """try to load the journal topic model (once)"""
        if self._model_loaded is not None:
            return self._model_loaded

        try:
            from topic_modeling.inference import TopicModelInference
            self._inference = TopicModelInference(model_type="journals")
            self._model_loaded = self._inference.load()
        except Exception as e:
            logger.warning(f"Could not load topic model: {e}")
            self._model_loaded = False

        if self._model_loaded:
            self._model_version = "bertopic"
            self._topic_info = self._inference.get_all_topic_info()
        else:
            logger.warning("Journal topic model not available — classify_topics() will raise")

        return self._model_loaded

    def get_input_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"

    def get_reports_dir(self) -> Path:
        reports_dir = self.settings.REPORTS_DIR / "bias"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()

        if not input_path.exists():
            raise FileNotFoundError(f"Processed journals not found: {input_path}")

        self.df = pd.read_parquet(input_path)
        self.slicer = DataSlicer(self.df)
        logger.info(f"Loaded {len(self.df)} journal entries for bias analysis")
        return self.df

    # topic classification

    def classify_topics(self) -> pd.DataFrame:
        """predict topics using bertopic model.
        model is required — raises RuntimeError if not available.
        adds topic_id, topic_label columns to self.df"""
        docs = self.df["content"].astype(str).tolist()

        if not self._ensure_model():
            raise RuntimeError(
                "Journal BERTopic model is required for bias analysis. "
                "Train the model first (DAG 1 train_journal_model task)."
            )

        topics, probs = self._inference.predict(docs)
        self.df["topic_id"] = topics
        self.df["topic_label"] = [
            self._inference.get_topic_label(int(t)) for t in topics
        ]
        if probs is not None:
            if len(probs.shape) > 1:
                self.df["topic_probability"] = np.max(probs, axis=1)
            else:
                self.df["topic_probability"] = probs
        else:
            self.df["topic_probability"] = 0.0

        logger.info(f"Classified {len(docs)} entries using BERTopic model")
        return self.df

    # patient distribution analysis

    def analyze_patient_distribution(self) -> Dict[str, Any]:
        patient_counts = self.df.groupby("patient_id").size()

        return {
            "total_patients": len(patient_counts),
            "entries_per_patient_mean": round(float(patient_counts.mean()), 2),
            "entries_per_patient_std": round(float(patient_counts.std()), 2),
            "entries_per_patient_min": int(patient_counts.min()),
            "entries_per_patient_max": int(patient_counts.max()),
            "entries_per_patient_median": float(patient_counts.median())
        }

    def find_sparse_patients(self) -> List[Dict[str, Any]]:
        patient_counts = self.df.groupby("patient_id").size()
        sparse = patient_counts[patient_counts < self.SPARSE_THRESHOLD]

        sparse_list = []
        for patient_id, count in sparse.items():
            sparse_list.append({
                "patient_id": str(patient_id),
                "entry_count": int(count)
            })

        return sparse_list

    # temporal patterns — entries by day/month, gap stats

    def analyze_temporal_patterns(self) -> Dict[str, Any]:
        patterns = {}

        if "day_of_week" in self.df.columns:
            day_counts = self.df["day_of_week"].value_counts().sort_index()
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            patterns["entries_by_day"] = {
                day_names[int(k)]: int(v) for k, v in day_counts.items() if pd.notna(k)
            }

        if "month" in self.df.columns:
            month_counts = self.df["month"].value_counts().sort_index()
            patterns["entries_by_month"] = {int(k): int(v) for k, v in month_counts.items() if pd.notna(k)}

        if "days_since_last" in self.df.columns:
            valid_gaps = self.df["days_since_last"][self.df["days_since_last"] > 0]
            if len(valid_gaps) > 0:
                patterns["entry_gap_mean"] = round(float(valid_gaps.mean()), 2)
                patterns["entry_gap_median"] = float(valid_gaps.median())
                patterns["entry_gap_max"] = int(valid_gaps.max())

        return patterns

    # topic distribution analysis

    def analyze_topic_distribution(self) -> Dict[str, Dict[str, Any]]:
        """analyze distribution of topics across entries"""
        total = len(self.df)
        valid_df = self.df[self.df["topic_id"] != -1]
        topic_stats = {}

        for topic_label, group in valid_df.groupby("topic_label"):
            count = len(group)
            percentage = (count / total * 100) if total > 0 else 0

            word_count_mean = 0
            if "word_count" in group.columns and count > 0:
                word_count_mean = float(group["word_count"].mean())

            topic_stats[str(topic_label)] = {
                "count": count,
                "percentage": round(percentage, 2),
                "word_count_mean": round(word_count_mean, 2),
            }

        return dict(sorted(topic_stats.items(), key=lambda x: -x[1]["count"]))

    # outlier analysis (replaces theme_overlap)

    def analyze_outlier_distribution(self) -> Dict[str, Any]:
        """analyze outlier (unclassified) entries"""
        total = len(self.df)
        outlier_mask = self.df["topic_id"] == -1
        outlier_count = int(outlier_mask.sum())

        result = {
            "outlier_count": outlier_count,
            "outlier_percentage": round(outlier_count / total * 100, 2) if total > 0 else 0,
            "classified_count": total - outlier_count,
        }

        # patient coverage: how many topics does each patient touch?
        if "patient_id" in self.df.columns:
            valid_df = self.df[~outlier_mask]
            if not valid_df.empty:
                patient_topic_counts = valid_df.groupby("patient_id")["topic_id"].nunique()
                result["avg_topics_per_patient"] = round(float(patient_topic_counts.mean()), 1)
                result["min_topics_per_patient"] = int(patient_topic_counts.min())
                result["max_topics_per_patient"] = int(patient_topic_counts.max())

        return result

    # patient topic coverage

    def analyze_patient_topic_coverage(self) -> Dict[str, Any]:
        """which topics does each patient write about?"""
        if "patient_id" not in self.df.columns:
            return {}

        valid_df = self.df[self.df["topic_id"] != -1]
        if valid_df.empty:
            return {}

        coverage = {}
        for patient_id, group in valid_df.groupby("patient_id"):
            topic_counts = group["topic_label"].value_counts()
            coverage[str(patient_id)] = {
                "num_topics": len(topic_counts),
                "top_topic": str(topic_counts.index[0]) if len(topic_counts) > 0 else "none",
                "topics": {str(t): int(c) for t, c in topic_counts.items()},
            }

        return coverage

    # visualizations

    def generate_visualizations(self, patient_dist: Dict, temporal: Dict,
                               topic_stats: Dict) -> List[Path]:
        saved_paths = []
        reports_dir = self.get_reports_dir()

        # entries by day
        if "entries_by_day" in temporal:
            plt.figure(figsize=(10, 5))
            days = list(temporal["entries_by_day"].keys())
            counts = list(temporal["entries_by_day"].values())

            plt.bar(days, counts, color='steelblue')
            plt.xlabel('Day of Week')
            plt.ylabel('Number of Entries')
            plt.title('Journal Entries by Day of Week')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            day_path = reports_dir / "journal_entries_by_day.png"
            plt.savefig(day_path, dpi=150)
            plt.close()
            saved_paths.append(day_path)

        # topic distribution bar chart
        if topic_stats:
            labels = list(topic_stats.keys())
            percentages = [topic_stats[t]["percentage"] for t in labels]

            # truncate long labels
            display_labels = [l[:30] + "..." if len(l) > 30 else l for l in labels]

            fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.4)))
            ax.barh(display_labels, percentages, color="#4a9eff")
            ax.set_xlabel('Percentage of Entries')
            ax.set_title(f'Topic Distribution in Journal Entries ({self._model_version})')
            ax.invert_yaxis()
            plt.tight_layout()

            theme_path = reports_dir / "journal_theme_distribution.png"
            fig.savefig(theme_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            saved_paths.append(theme_path)

        # entries by month
        if "entries_by_month" in temporal:
            plt.figure(figsize=(10, 5))
            months = list(temporal["entries_by_month"].keys())
            counts = list(temporal["entries_by_month"].values())

            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_labels = [month_names[m-1] if 1 <= m <= 12 else str(m) for m in months]

            plt.bar(month_labels, counts, color='teal')
            plt.xlabel('Month')
            plt.ylabel('Number of Entries')
            plt.title('Journal Entries by Month')
            plt.tight_layout()

            month_path = reports_dir / "journal_entries_by_month.png"
            plt.savefig(month_path, dpi=150)
            plt.close()
            saved_paths.append(month_path)

        logger.info(f"Generated {len(saved_paths)} visualizations")
        return saved_paths

    # mitigation notes with bias type labels

    def generate_mitigation_notes(self, sparse_patients: List,
                                  temporal: Dict, topic_stats: Dict,
                                  patient_dist: Dict,
                                  outlier_analysis: Dict) -> List[str]:
        notes = []

        # patient representation analysis
        if patient_dist:
            std = patient_dist.get("entries_per_patient_std", 0)
            if std > 20:
                notes.append(
                    f"REPRESENTATION BIAS: High variance in entries per patient (std={std}). "
                    f"Some patients are over/under-represented. "
                    f"Consider re-sampling or weighting to balance patient representation."
                )

        if sparse_patients:
            patient_ids = [p["patient_id"] for p in sparse_patients[:5]]
            notes.append(
                f"REPRESENTATION BIAS: {len(sparse_patients)} patients with fewer than "
                f"{self.SPARSE_THRESHOLD} entries ({', '.join(patient_ids)}). "
                f"These patients may be underrepresented in downstream analysis. "
                f"Consider collecting more entries or applying upsampling."
            )

        # temporal analysis
        if "entry_gap_max" in temporal and temporal["entry_gap_max"] > 30:
            notes.append(
                f"TEMPORAL BIAS: Maximum gap of {temporal['entry_gap_max']} days between entries. "
                f"Large gaps may indicate disengagement or crisis periods that skew temporal analysis."
            )

        if "entry_gap_mean" in temporal:
            notes.append(
                f"Temporal pattern: Average entry gap is {temporal['entry_gap_mean']} days "
                f"(median: {temporal.get('entry_gap_median', 'N/A')}). "
                f"Consistent journaling frequency supports reliable temporal analysis."
            )

        # topic balance analysis
        if topic_stats:
            percentages = {t: s.get("percentage", 0) for t, s in topic_stats.items()}
            if percentages:
                max_topic = max(percentages, key=percentages.get)
                min_topic = min(percentages, key=percentages.get)
                max_pct = percentages[max_topic]
                min_pct = percentages[min_topic]

                if min_pct > 0 and max_pct > 3 * min_pct:
                    notes.append(
                        f"REPRESENTATION BIAS: Topic imbalance — '{max_topic}' ({max_pct}%) "
                        f"is {round(max_pct / min_pct, 1)}x more frequent than '{min_topic}' ({min_pct}%). "
                        f"Consider augmenting underrepresented topics for balanced RAG retrieval."
                    )

        # outlier analysis
        if outlier_analysis:
            outlier_pct = outlier_analysis.get("outlier_percentage", 0)
            if outlier_pct > 15:
                notes.append(
                    f"MODEL QUALITY: {outlier_pct}% of entries are outliers (unclassified). "
                    f"Consider adjusting model hyperparameters or re-training with more data."
                )
            elif outlier_pct > 30:
                notes.append(
                    f"COVERAGE GAP: {outlier_pct}% of entries match no topic. "
                    f"The topic model may need re-training or hyperparameter tuning."
                )

        # model version note
        if self._model_version != "bertopic":
            notes.append(
                "NOTE: Topic model is not loaded. "
                "Train a BERTopic model for accurate, data-driven topic discovery."
            )

        if not notes:
            notes.append(
                "No significant bias detected. Patient distribution, topic balance, "
                "and temporal patterns appear balanced across the dataset."
            )

        return notes

    def generate_report(self, patient_dist: Dict, temporal: Dict,
                       topic_stats: Dict, outlier_analysis: Dict,
                       sparse_patients: List, patient_topic_coverage: Dict,
                       mitigation_notes: List) -> JournalBiasReport:
        return JournalBiasReport(
            dataset_name="journals",
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_records=len(self.df),
            total_patients=self.df["patient_id"].nunique() if "patient_id" in self.df.columns else 0,
            model_version=self._model_version,
            patient_distribution=patient_dist,
            temporal_patterns=temporal,
            topic_distribution=topic_stats,
            outlier_analysis=outlier_analysis,
            sparse_patients=sparse_patients,
            patient_topic_coverage=patient_topic_coverage,
            mitigation_notes=mitigation_notes,
        )

    def save_report(self, report: JournalBiasReport) -> Path:
        output_path = self.get_reports_dir() / "journal_bias_report.json"
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        logger.info(f"Saved bias report to {output_path}")
        return output_path

    def run(self, skip_existing: bool = True) -> Optional[JournalBiasReport]:
        self.settings.ensure_directories()

        report_path = self.get_reports_dir() / "journal_bias_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None

        self.load_data()
        self.classify_topics()

        patient_dist = self.analyze_patient_distribution()
        temporal = self.analyze_temporal_patterns()
        topic_stats = self.analyze_topic_distribution()
        outlier_analysis = self.analyze_outlier_distribution()
        sparse_patients = self.find_sparse_patients()
        patient_topic_coverage = self.analyze_patient_topic_coverage()
        mitigation_notes = self.generate_mitigation_notes(
            sparse_patients, temporal, topic_stats, patient_dist, outlier_analysis
        )

        self.generate_visualizations(patient_dist, temporal, topic_stats)

        report = self.generate_report(
            patient_dist, temporal, topic_stats, outlier_analysis,
            sparse_patients, patient_topic_coverage, mitigation_notes
        )
        self.save_report(report)

        logger.info(f"Bias analysis complete. Found {len(sparse_patients)} sparse patients")
        return report


if __name__ == "__main__":
    analyzer = JournalBiasAnalyzer()
    analyzer.run(skip_existing=False)
