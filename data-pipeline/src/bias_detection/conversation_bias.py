# bias analysis for the conversations dataset
# uses bertopic model inference for topic-based bias analysis
# model is required — trained in dag 1 before bias tasks run
# severity classification uses bertopic severity model (replaces keyword-based)
# analyzes response length by topic, outliers, and generates visualizations + mitigation notes

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
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

from .slicer import DataSlicer, SliceStats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BiasReport:
    dataset_name: str
    timestamp: str
    total_records: int
    model_version: str
    topic_distribution: Dict[str, Dict[str, Any]]
    severity_distribution: Dict[str, Dict[str, Any]]
    underrepresented_topics: List[str]
    cross_analysis: Dict[str, Any]
    outlier_analysis: Dict[str, Any]
    mitigation_notes: List[str]


class ConversationBiasAnalyzer:

    # topics below this % are flagged as underrepresented
    UNDERREPRESENTATION_THRESHOLD = 3.0

    def __init__(self):
        self.settings = config.settings
        self.df = None
        self.slicer = None
        self._inference = None
        self._model_loaded: Optional[bool] = None
        self._topic_info: List[Dict[str, Any]] = []
        self._model_version = "not_loaded"

    def _ensure_model(self) -> bool:
        """try to load the conversation topic model (once)"""
        if self._model_loaded is not None:
            return self._model_loaded

        try:
            from topic_modeling.inference import TopicModelInference
            self._inference = TopicModelInference(model_type="conversations")
            self._model_loaded = self._inference.load()
        except Exception as e:
            logger.warning(f"Could not load topic model: {e}")
            self._model_loaded = False

        if self._model_loaded:
            self._model_version = "bertopic"
            self._topic_info = self._inference.get_all_topic_info()
        else:
            logger.warning("Conversation topic model not available — classify_topics() will raise")

        return self._model_loaded

    def get_input_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "conversations" / "processed_conversations.parquet"

    def get_reports_dir(self) -> Path:
        reports_dir = self.settings.REPORTS_DIR / "bias"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()

        if not input_path.exists():
            raise FileNotFoundError(f"Processed conversations not found: {input_path}")

        self.df = pd.read_parquet(input_path)
        self.slicer = DataSlicer(self.df)
        logger.info(f"Loaded {len(self.df)} conversations for bias analysis")
        return self.df

    # topic classification

    def classify_topics(self) -> pd.DataFrame:
        """predict topics using bertopic model.
        model is required — raises RuntimeError if not available.
        adds topic_id, topic_label, topic_probability columns to self.df"""
        docs = self.df["context"].astype(str).tolist()

        if not self._ensure_model():
            raise RuntimeError(
                "Conversation BERTopic model is required for bias analysis. "
                "Train the model first (DAG 1 train_conversation_model task)."
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

        logger.info(f"Classified {len(docs)} conversations using BERTopic model")
        return self.df

    # severity classification (bertopic severity model)

    def classify_severity(self) -> pd.DataFrame:
        """classify severity using bertopic severity model.
        loads the severity model and predicts severity for all conversations.
        falls back to 'unknown' when model is not available."""
        try:
            from topic_modeling.inference import TopicModelInference
            severity_inference = TopicModelInference(model_type="severity")
            if severity_inference.load():
                contexts = self.df["context"].astype(str).tolist()
                self.df["severity"] = severity_inference.predict_severity(contexts)
                logger.info(f"Classified severity for {len(contexts)} conversations using BERTopic model")
            else:
                logger.warning("Severity BERTopic model not available — all conversations marked 'unknown'")
                self.df["severity"] = "unknown"
        except Exception as e:
            logger.warning(f"Severity classification failed: {e}")
            self.df["severity"] = "unknown"
        return self.df

    # analysis

    def analyze_topic_distribution(self) -> Dict[str, Dict[str, Any]]:
        """analyze distribution of topics across conversations"""
        total = len(self.df)
        valid_df = self.df[self.df["topic_id"] != -1]
        topic_stats = {}

        for topic_label, group in valid_df.groupby("topic_label"):
            count = len(group)
            percentage = (count / total * 100) if total > 0 else 0

            response_length_mean = 0
            if "response_word_count" in group.columns and count > 0:
                response_length_mean = float(group["response_word_count"].mean())

            topic_stats[str(topic_label)] = {
                "count": count,
                "percentage": round(percentage, 2),
                "response_length_mean": round(response_length_mean, 2),
            }

        return dict(sorted(topic_stats.items(), key=lambda x: -x[1]["count"]))

    def analyze_severity_distribution(self) -> Dict[str, Dict[str, Any]]:
        slicer = DataSlicer(self.df)
        severity_slices = slicer.slice_by_category("severity")
        severity_stats = {}
        total = len(self.df)

        for severity in ["crisis", "severe", "moderate", "mild", "unknown"]:
            severity_df = severity_slices.get(severity, pd.DataFrame())
            count = len(severity_df)
            percentage = (count / total * 100) if total > 0 else 0

            response_length_mean = 0
            if "response_word_count" in severity_df.columns and count > 0:
                response_length_mean = float(severity_df["response_word_count"].mean())

            severity_stats[severity] = {
                "count": count,
                "percentage": round(percentage, 2),
                "response_length_mean": round(response_length_mean, 2)
            }

        return severity_stats

    def find_underrepresented_topics(self, topic_stats: Dict[str, Dict[str, Any]]) -> List[str]:
        underrepresented = []
        for topic, stats in topic_stats.items():
            if stats["percentage"] < self.UNDERREPRESENTATION_THRESHOLD:
                underrepresented.append(topic)
        return underrepresented

    # checks which topics get noticeably shorter/longer responses
    def cross_analyze(self, topic_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        overall_response_mean = 0
        if "response_word_count" in self.df.columns:
            overall_response_mean = float(self.df["response_word_count"].mean())

        shorter_response_topics = []
        longer_response_topics = []

        for topic, stats in topic_stats.items():
            if stats["count"] < 10:
                continue

            diff = stats["response_length_mean"] - overall_response_mean
            if diff < -20:
                shorter_response_topics.append({
                    "topic": topic,
                    "response_mean": stats["response_length_mean"],
                    "diff_from_overall": round(diff, 2)
                })
            elif diff > 20:
                longer_response_topics.append({
                    "topic": topic,
                    "response_mean": stats["response_length_mean"],
                    "diff_from_overall": round(diff, 2)
                })

        return {
            "overall_response_mean": round(overall_response_mean, 2),
            "shorter_response_topics": shorter_response_topics,
            "longer_response_topics": longer_response_topics
        }

    # outlier analysis (replaces topic_overlap)

    def analyze_outlier_distribution(self) -> Dict[str, Any]:
        """analyze outlier (unclassified) conversations"""
        total = len(self.df)
        outlier_mask = self.df["topic_id"] == -1
        outlier_count = int(outlier_mask.sum())

        result = {
            "outlier_count": outlier_count,
            "outlier_percentage": round(outlier_count / total * 100, 2) if total > 0 else 0,
            "classified_count": total - outlier_count,
        }

        # unique topics across classified entries
        valid_df = self.df[~outlier_mask]
        if not valid_df.empty:
            result["unique_topics"] = int(valid_df["topic_id"].nunique())
            result["avg_probability"] = round(float(valid_df["topic_probability"].mean()), 3)

        return result

    # visualizations

    def generate_visualizations(self, topic_stats: Dict, severity_stats: Dict) -> List[Path]:
        saved_paths = []
        reports_dir = self.get_reports_dir()

        # topic distribution bar chart
        if topic_stats:
            labels = list(topic_stats.keys())
            percentages = [topic_stats[t]["percentage"] for t in labels]
            display_labels = [l[:30] + "..." if len(l) > 30 else l for l in labels]

            fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.4)))
            ax.barh(display_labels, percentages, color='steelblue')
            ax.axvline(x=self.UNDERREPRESENTATION_THRESHOLD, color='red',
                       linestyle='--', label=f'Threshold ({self.UNDERREPRESENTATION_THRESHOLD}%)')
            ax.set_xlabel('Percentage of Conversations')
            ax.set_title(f'Topic Distribution in Conversations ({self._model_version})')
            ax.legend()
            ax.invert_yaxis()
            plt.tight_layout()

            topic_path = reports_dir / "topic_distribution.png"
            fig.savefig(topic_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            saved_paths.append(topic_path)

        # severity pie chart (bertopic severity model)
        plt.figure(figsize=(8, 8))
        severities = list(severity_stats.keys())
        counts = [severity_stats[s]["count"] for s in severities]

        colors = {
            "crisis": "#d62728",
            "severe": "#ff7f0e",
            "moderate": "#ffbb78",
            "mild": "#98df8a",
            "unknown": "#c7c7c7"
        }
        pie_colors = [colors.get(s, "#c7c7c7") for s in severities]

        plt.pie(counts, labels=severities, autopct='%1.1f%%', colors=pie_colors)
        plt.title('Severity Distribution')
        plt.tight_layout()

        severity_path = reports_dir / "severity_distribution.png"
        plt.savefig(severity_path, dpi=150)
        plt.close()
        saved_paths.append(severity_path)

        # response length by topic
        if topic_stats:
            labels = list(topic_stats.keys())
            response_means = [topic_stats[t]["response_length_mean"] for t in labels]
            display_labels = [l[:25] + "..." if len(l) > 25 else l for l in labels]

            plt.figure(figsize=(12, 6))
            plt.bar(display_labels, response_means, color='teal')
            plt.xticks(rotation=45, ha='right')
            plt.ylabel('Average Response Word Count')
            plt.title(f'Response Length by Topic ({self._model_version})')
            plt.tight_layout()

            response_path = reports_dir / "response_length_by_topic.png"
            plt.savefig(response_path, dpi=150)
            plt.close()
            saved_paths.append(response_path)

        logger.info(f"Generated {len(saved_paths)} visualizations")
        return saved_paths

    # mitigation notes with bias type labels

    def generate_mitigation_notes(self, underrepresented: List[str],
                                  cross_analysis: Dict,
                                  outlier_analysis: Dict) -> List[str]:
        notes = []

        if underrepresented:
            notes.append(
                f"REPRESENTATION BIAS: Underrepresented topics ({', '.join(underrepresented)}): "
                f"Consider collecting more data for these topics to improve RAG coverage. "
                f"Certain clinical concerns have fewer examples in the dataset."
            )

        if cross_analysis.get("shorter_response_topics"):
            topics = [t["topic"] for t in cross_analysis["shorter_response_topics"]]
            notes.append(
                f"RESPONSE BIAS: Topics with shorter responses ({', '.join(topics)}): "
                f"May indicate lower counselor engagement on these topics. "
                f"Review if response quality is adequate for RAG retrieval."
            )

        if cross_analysis.get("longer_response_topics"):
            topics = [t["topic"] for t in cross_analysis["longer_response_topics"]]
            notes.append(
                f"RESPONSE BIAS: Topics with longer responses ({', '.join(topics)}): "
                f"Verbosity may affect RAG retrieval quality. "
                f"Consider chunking long responses for better embedding coverage."
            )

        # outlier analysis
        if outlier_analysis:
            outlier_pct = outlier_analysis.get("outlier_percentage", 0)
            if outlier_pct > 15:
                notes.append(
                    f"MODEL QUALITY: {outlier_pct}% of conversations are outliers (unclassified). "
                    f"Consider adjusting model hyperparameters or re-training with more data."
                )

        # model version note
        if self._model_version != "bertopic":
            notes.append(
                "NOTE: Topic model is not loaded. "
                "Train a BERTopic model for accurate, data-driven topic discovery."
            )

        if not notes:
            notes.append(
                "No significant bias detected. Topic distribution, response quality, "
                "and severity distribution appear balanced."
            )

        return notes

    def generate_report(self, topic_stats: Dict, severity_stats: Dict,
                       underrepresented: List[str], cross_analysis: Dict,
                       outlier_analysis: Dict,
                       mitigation_notes: List[str]) -> BiasReport:
        return BiasReport(
            dataset_name="conversations",
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_records=len(self.df),
            model_version=self._model_version,
            topic_distribution=topic_stats,
            severity_distribution=severity_stats,
            underrepresented_topics=underrepresented,
            cross_analysis=cross_analysis,
            outlier_analysis=outlier_analysis,
            mitigation_notes=mitigation_notes,
        )

    def save_report(self, report: BiasReport) -> Path:
        output_path = self.get_reports_dir() / "conversation_bias_report.json"
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        logger.info(f"Saved bias report to {output_path}")
        return output_path

    def run(self, skip_existing: bool = True) -> Optional[BiasReport]:
        self.settings.ensure_directories()

        report_path = self.get_reports_dir() / "conversation_bias_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None

        self.load_data()
        self.classify_topics()
        self.classify_severity()

        topic_stats = self.analyze_topic_distribution()
        severity_stats = self.analyze_severity_distribution()
        underrepresented = self.find_underrepresented_topics(topic_stats)
        cross_analysis = self.cross_analyze(topic_stats)
        outlier_analysis = self.analyze_outlier_distribution()
        mitigation_notes = self.generate_mitigation_notes(underrepresented, cross_analysis, outlier_analysis)

        self.generate_visualizations(topic_stats, severity_stats)

        report = self.generate_report(
            topic_stats, severity_stats, underrepresented,
            cross_analysis, outlier_analysis, mitigation_notes
        )
        self.save_report(report)

        logger.info(f"Bias analysis complete. Found {len(underrepresented)} underrepresented topics")
        return report


if __name__ == "__main__":
    analyzer = ConversationBiasAnalyzer()
    analyzer.run(skip_existing=False)
