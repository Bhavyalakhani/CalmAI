# model validation and quality metrics
# evaluates topic model quality: diversity, coherence, outlier ratio, label quality
# generates json reports for audit trail

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import get_reports_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# quality thresholds
THRESHOLDS = {
    "min_topics": 3,
    "max_topics": 150,
    "max_outlier_ratio": 0.15,
    "min_topic_diversity": 0.5,
    "min_avg_topic_size": 5,
    "min_label_unique_ratio": 0.8,
}


class TopicModelValidator:
    """validates topic model quality and generates reports"""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = {**THRESHOLDS, **(thresholds or {})}

    def validate(
        self,
        training_result: Dict[str, Any],
        docs: Optional[List[str]] = None,
        model=None,
    ) -> Dict[str, Any]:
        """run full validation suite on a training result.

        args:
            training_result: output from TopicModelTrainer.train()
            docs: original documents (for coherence checks)
            model: the bertopic model instance (for advanced metrics)

        returns:
            validation report dict with metrics, checks, pass/fail status
        """
        topic_info = training_result.get("topic_info", [])
        num_topics = training_result.get("num_topics", 0)
        num_documents = training_result.get("num_documents", 0)
        outlier_ratio = training_result.get("outlier_ratio", 1.0)

        # compute all metrics
        metrics = {}
        checks = []

        # basic counts
        metrics["num_topics"] = num_topics
        metrics["num_documents"] = num_documents
        metrics["outlier_ratio"] = outlier_ratio
        metrics["outlier_count"] = training_result.get("outlier_count", 0)

        # topic count check
        checks.append({
            "name": "topic_count_range",
            "passed": self.thresholds["min_topics"] <= num_topics <= self.thresholds["max_topics"],
            "expected": f"{self.thresholds['min_topics']}-{self.thresholds['max_topics']}",
            "actual": num_topics,
            "message": f"Found {num_topics} topics",
        })

        # outlier ratio check
        checks.append({
            "name": "outlier_ratio",
            "passed": outlier_ratio <= self.thresholds["max_outlier_ratio"],
            "expected": f"<= {self.thresholds['max_outlier_ratio']}",
            "actual": round(outlier_ratio, 4),
            "message": f"Outlier ratio: {outlier_ratio:.2%}",
        })

        # topic diversity
        diversity = self._compute_topic_diversity(topic_info)
        metrics["topic_diversity"] = diversity
        checks.append({
            "name": "topic_diversity",
            "passed": diversity >= self.thresholds["min_topic_diversity"],
            "expected": f">= {self.thresholds['min_topic_diversity']}",
            "actual": round(diversity, 4),
            "message": f"Topic diversity: {diversity:.3f}",
        })

        # average topic size
        avg_size = self._compute_avg_topic_size(topic_info)
        metrics["avg_topic_size"] = avg_size
        checks.append({
            "name": "avg_topic_size",
            "passed": avg_size >= self.thresholds["min_avg_topic_size"],
            "expected": f">= {self.thresholds['min_avg_topic_size']}",
            "actual": round(avg_size, 1),
            "message": f"Average topic size: {avg_size:.1f} documents",
        })

        # label quality (uniqueness)
        label_quality = self._compute_label_quality(topic_info)
        metrics["label_unique_ratio"] = label_quality["unique_ratio"]
        metrics["label_non_empty_ratio"] = label_quality["non_empty_ratio"]
        checks.append({
            "name": "label_uniqueness",
            "passed": label_quality["unique_ratio"] >= self.thresholds["min_label_unique_ratio"],
            "expected": f">= {self.thresholds['min_label_unique_ratio']}",
            "actual": round(label_quality["unique_ratio"], 4),
            "message": f"Label uniqueness: {label_quality['unique_ratio']:.2%}",
        })

        # topic size distribution (gini coefficient — lower is more balanced)
        gini = self._compute_size_gini(topic_info)
        metrics["topic_size_gini"] = gini

        # composite score
        composite = self._compute_composite_score(metrics)
        metrics["composite_score"] = composite

        # overall pass/fail
        all_passed = all(c["passed"] for c in checks)

        report = {
            "model_type": training_result.get("model_type", "unknown"),
            "status": "pass" if all_passed else "fail",
            "metrics": metrics,
            "checks": checks,
            "topic_summary": self._build_topic_summary(topic_info),
            "thresholds": self.thresholds,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Validation {'PASSED' if all_passed else 'FAILED'}: {len([c for c in checks if c['passed']])}/{len(checks)} checks")
        return report

    def _compute_topic_diversity(self, topic_info: List[Dict]) -> float:
        """fraction of unique words across all topic keyword lists.
        higher = more diverse topics (less overlap).
        """
        if not topic_info:
            return 0.0

        all_words = []
        for t in topic_info:
            all_words.extend(t.get("keywords", []))

        if not all_words:
            return 0.0

        return len(set(all_words)) / len(all_words)

    def _compute_avg_topic_size(self, topic_info: List[Dict]) -> float:
        """average number of documents per topic"""
        if not topic_info:
            return 0.0
        counts = [t.get("count", 0) for t in topic_info]
        return float(np.mean(counts)) if counts else 0.0

    def _compute_label_quality(self, topic_info: List[Dict]) -> Dict[str, float]:
        """evaluate label quality: uniqueness and non-empty ratio"""
        if not topic_info:
            return {"unique_ratio": 0.0, "non_empty_ratio": 0.0}

        labels = []
        for t in topic_info:
            label = t.get("llm_label") or t.get("keybert_label") or t.get("name", "")
            labels.append(str(label).strip())

        non_empty = [l for l in labels if l]
        unique = set(non_empty)

        return {
            "unique_ratio": len(unique) / len(labels) if labels else 0.0,
            "non_empty_ratio": len(non_empty) / len(labels) if labels else 0.0,
        }

    def _compute_size_gini(self, topic_info: List[Dict]) -> float:
        """compute gini coefficient of topic sizes.
        0 = perfectly balanced, 1 = all docs in one topic.
        """
        if not topic_info:
            return 0.0

        sizes = np.array([t.get("count", 0) for t in topic_info], dtype=float)
        if len(sizes) <= 1 or sizes.sum() == 0:
            return 0.0

        sizes = np.sort(sizes)
        n = len(sizes)
        index = np.arange(1, n + 1)
        return float((2 * np.sum(index * sizes) - (n + 1) * np.sum(sizes)) / (n * np.sum(sizes)))

    def _compute_composite_score(self, metrics: Dict[str, float]) -> float:
        """weighted composite score combining all metrics.
        range: 0.0 to 1.0 where higher is better.
        """
        num_topics = metrics.get("num_topics", 0)
        outlier_ratio = metrics.get("outlier_ratio", 1.0)
        diversity = metrics.get("topic_diversity", 0.0)
        gini = metrics.get("topic_size_gini", 1.0)

        # topic count score
        if 5 <= num_topics <= 25:
            topic_score = 1.0
        elif 3 <= num_topics < 5 or 25 < num_topics <= 40:
            topic_score = 0.6
        else:
            topic_score = 0.2

        # outlier score (lower is better)
        outlier_score = max(0, 1.0 - outlier_ratio * 4)

        # balance score (lower gini is more balanced)
        balance_score = max(0, 1.0 - gini)

        composite = (
            topic_score * 0.25
            + outlier_score * 0.30
            + diversity * 0.25
            + balance_score * 0.20
        )
        return round(composite, 4)

    def _build_topic_summary(self, topic_info: List[Dict]) -> List[Dict[str, Any]]:
        """build a concise summary of each topic for the report"""
        summary = []
        for t in topic_info:
            label = t.get("llm_label") or t.get("keybert_label") or t.get("name", "")
            summary.append({
                "topic_id": t.get("topic_id"),
                "label": str(label).strip(),
                "keywords": t.get("keywords", [])[:5],
                "count": t.get("count", 0),
            })
        return sorted(summary, key=lambda x: -x["count"])

    def save_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> Path:
        """save validation report as json"""
        reports_dir = get_reports_dir()
        model_type = report.get("model_type", "unknown")
        fname = filename or f"{model_type}_validation_report.json"
        path = reports_dir / fname

        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Validation report saved to {path}")
        return path
