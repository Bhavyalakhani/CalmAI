# model validation and quality metrics
# evaluates topic model quality: diversity, coherence, outlier ratio, label quality
# includes clustering quality metrics (silhouette, calinski-harabasz, davies-bouldin, dbcv)
# supports holdout evaluation and candidate-vs-active comparison
# generates json reports for audit trail

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
from .config import get_reports_dir  # noqa: E402

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

        passed_count = len([c for c in checks if c['passed']])
        status = 'PASSED' if all_passed else 'FAILED'
        logger.info(f"Validation {status}: {passed_count}/{len(checks)} checks")
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

        non_empty = [lab for lab in labels if lab]
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

    def compute_clustering_metrics(
        self,
        topics: List[int],
        embeddings: np.ndarray,
    ) -> Dict[str, float]:
        """compute clustering quality metrics on UMAP-reduced embeddings.

        metrics computed:
        - silhouette_score: cohesion vs separation (-1 to 1, higher is better)
        - calinski_harabasz: ratio of between/within cluster dispersion (higher is better)
        - davies_bouldin: average similarity between clusters (lower is better)
        - dbcv: density-based cluster validity for HDBSCAN (higher is better)

        args:
            topics: list of topic assignments (may include -1 for outliers)
            embeddings: 2d embeddings (UMAP output or raw embeddings)

        returns:
            dict of metric name -> value
        """
        from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

        topics_arr = np.array(topics)
        metrics = {}

        # filter out outliers (topic == -1) for cluster quality metrics
        non_outlier_mask = topics_arr != -1
        valid_topics = topics_arr[non_outlier_mask]
        valid_embeddings = embeddings[non_outlier_mask]

        n_clusters = len(set(valid_topics))

        if n_clusters < 2 or len(valid_topics) < n_clusters + 1:
            logger.warning(
                f"Not enough clusters ({n_clusters}) or samples ({len(valid_topics)}) "
                "for clustering metrics — returning defaults"
            )
            metrics["silhouette_score"] = 0.0
            metrics["calinski_harabasz"] = 0.0
            metrics["davies_bouldin"] = float("inf")
            metrics["dbcv_score"] = 0.0
            return metrics

        # silhouette score
        try:
            metrics["silhouette_score"] = round(
                float(silhouette_score(valid_embeddings, valid_topics)), 4
            )
            logger.info(f"Silhouette score: {metrics['silhouette_score']}")
        except Exception as e:
            logger.warning(f"Silhouette score failed: {e}")
            metrics["silhouette_score"] = 0.0

        # calinski-harabasz index
        try:
            metrics["calinski_harabasz"] = round(
                float(calinski_harabasz_score(valid_embeddings, valid_topics)), 4
            )
            logger.info(f"Calinski-Harabasz: {metrics['calinski_harabasz']}")
        except Exception as e:
            logger.warning(f"Calinski-Harabasz failed: {e}")
            metrics["calinski_harabasz"] = 0.0

        # davies-bouldin index (lower is better)
        try:
            metrics["davies_bouldin"] = round(
                float(davies_bouldin_score(valid_embeddings, valid_topics)), 4
            )
            logger.info(f"Davies-Bouldin: {metrics['davies_bouldin']}")
        except Exception as e:
            logger.warning(f"Davies-Bouldin failed: {e}")
            metrics["davies_bouldin"] = float("inf")

        # DBCV — density-based cluster validity (most principled for HDBSCAN)
        try:
            from hdbscan.validity import validity_index
            dbcv = validity_index(
                valid_embeddings.astype(np.float64), valid_topics.astype(np.intp)
            )
            metrics["dbcv_score"] = round(float(dbcv), 4)
            logger.info(f"DBCV: {metrics['dbcv_score']}")
        except ImportError:
            logger.warning("hdbscan.validity not available — skipping DBCV")
            metrics["dbcv_score"] = 0.0
        except Exception as e:
            logger.warning(f"DBCV failed: {e}")
            metrics["dbcv_score"] = 0.0

        return metrics

    def compute_agreement_metrics(
        self,
        candidate_topics: List[int],
        active_topics: List[int],
    ) -> Dict[str, float]:
        """compute agreement metrics between candidate and active model predictions
        on the same holdout documents.

        metrics:
        - nmi: normalized mutual information (0 to 1)
        - ari: adjusted rand index (-1 to 1)
        - v_measure: harmonic mean of homogeneity and completeness (0 to 1)

        args:
            candidate_topics: topic assignments from candidate model
            active_topics: topic assignments from active model

        returns:
            dict of metric name -> value
        """
        from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score, v_measure_score

        metrics = {}

        if len(candidate_topics) != len(active_topics):
            logger.warning("Topic list lengths differ — cannot compute agreement metrics")
            return {"nmi": 0.0, "ari": 0.0, "v_measure": 0.0}

        if len(candidate_topics) == 0:
            return {"nmi": 0.0, "ari": 0.0, "v_measure": 0.0}

        try:
            metrics["nmi"] = round(
                float(normalized_mutual_info_score(active_topics, candidate_topics)), 4
            )
        except Exception as e:
            logger.warning(f"NMI computation failed: {e}")
            metrics["nmi"] = 0.0

        try:
            metrics["ari"] = round(
                float(adjusted_rand_score(active_topics, candidate_topics)), 4
            )
        except Exception as e:
            logger.warning(f"ARI computation failed: {e}")
            metrics["ari"] = 0.0

        try:
            metrics["v_measure"] = round(
                float(v_measure_score(active_topics, candidate_topics)), 4
            )
        except Exception as e:
            logger.warning(f"V-measure computation failed: {e}")
            metrics["v_measure"] = 0.0

        logger.info(
            f"Agreement metrics: NMI={metrics['nmi']}, ARI={metrics['ari']}, "
            f"V-measure={metrics['v_measure']}"
        )
        return metrics

    def validate_holdout(
        self,
        candidate_model,
        holdout_docs: List[str],
        holdout_embeddings: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """validate a candidate model against holdout documents.

        args:
            candidate_model: fitted BERTopic model
            holdout_docs: list of holdout documents
            holdout_embeddings: pre-calculated embeddings for holdout docs

        returns:
            validation report dict with clustering + topic quality metrics
        """
        logger.info(f"Validating candidate on {len(holdout_docs)} holdout documents")

        # predict on holdout
        topics, probs = candidate_model.transform(holdout_docs, holdout_embeddings)

        topics_arr = np.array(topics)
        outlier_count = int((topics_arr == -1).sum())
        outlier_ratio = outlier_count / len(holdout_docs) if holdout_docs else 0

        # get topic info from the model
        topic_info_df = candidate_model.get_topic_info()
        num_topics = len(topic_info_df[topic_info_df["Topic"] != -1])

        # build topic_info list for existing metric methods
        topic_info = []
        for _, row in topic_info_df.iterrows():
            tid = int(row["Topic"])
            if tid == -1:
                continue
            topic_words = candidate_model.get_topic(tid)
            keywords = [w for w, _ in topic_words[:10]] if topic_words else []
            topic_info.append({
                "topic_id": tid,
                "count": int((topics_arr == tid).sum()),
                "keywords": keywords,
                "name": str(row.get("Name", "")),
            })

        # compute standard metrics via validate()
        training_result = {
            "model_type": "holdout",
            "num_topics": num_topics,
            "num_documents": len(holdout_docs),
            "outlier_count": outlier_count,
            "outlier_ratio": round(outlier_ratio, 4),
            "topic_info": topic_info,
        }
        report = self.validate(training_result)
        report["dataset_split"] = "holdout"

        # compute clustering metrics if embeddings available
        if holdout_embeddings is not None and len(holdout_embeddings) > 0:
            clustering = self.compute_clustering_metrics(topics, holdout_embeddings)
            report["metrics"].update(clustering)

            # recompute composite with silhouette included
            report["metrics"]["composite_score"] = self._compute_composite_score_v2(
                report["metrics"]
            )

        report["holdout_topics"] = topics
        logger.info(
            f"Holdout validation: {num_topics} topics, outlier_ratio={outlier_ratio:.2%}, "
            f"silhouette={report['metrics'].get('silhouette_score', 'N/A')}"
        )
        return report

    def compare_candidate_vs_active(
        self,
        candidate_report: Dict[str, Any],
        active_report: Dict[str, Any],
        holdout_docs: Optional[List[str]] = None,
        candidate_model=None,
        active_model=None,
        holdout_embeddings: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """compare candidate model against the active model.

        if both models and holdout_docs are provided, computes agreement metrics
        (NMI, ARI, V-measure) between their predictions on the same holdout set.

        args:
            candidate_report: validation report from candidate model
            active_report: validation report from active model
            holdout_docs: documents to predict on for agreement metrics
            candidate_model: candidate BERTopic model
            active_model: active BERTopic model
            holdout_embeddings: pre-calculated embeddings for holdout docs

        returns:
            comparison dict with per-metric deltas and agreement scores
        """
        logger.info("Comparing candidate vs active model")

        candidate_metrics = candidate_report.get("metrics", {})
        active_metrics = active_report.get("metrics", {})

        # per-metric delta: candidate - active (positive = candidate is better)
        comparison_keys = [
            "silhouette_score", "outlier_ratio", "topic_diversity",
            "topic_size_gini", "composite_score", "calinski_harabasz",
            "davies_bouldin", "dbcv_score",
        ]
        deltas = {}
        for key in comparison_keys:
            c_val = candidate_metrics.get(key)
            a_val = active_metrics.get(key)
            if c_val is not None and a_val is not None:
                deltas[key] = round(c_val - a_val, 4)

        result = {
            "candidate_metrics": candidate_metrics,
            "active_metrics": active_metrics,
            "deltas": deltas,
        }

        # agreement metrics between candidate and active predictions
        if (
            holdout_docs is not None
            and candidate_model is not None
            and active_model is not None
        ):
            candidate_topics = candidate_report.get("holdout_topics")
            if candidate_topics is None:
                candidate_topics, _ = candidate_model.transform(
                    holdout_docs, holdout_embeddings
                )

            active_topics, _ = active_model.transform(holdout_docs, holdout_embeddings)

            agreement = self.compute_agreement_metrics(
                list(candidate_topics), list(active_topics)
            )
            result["agreement"] = agreement
        else:
            result["agreement"] = {}

        logger.info(f"Comparison deltas: {deltas}")
        return result

    def _compute_composite_score_v2(self, metrics: Dict[str, float]) -> float:
        """enhanced composite score incorporating silhouette and agreement.

        formula:
            0.25 * silhouette_norm
          + 0.25 * (1 - outlier_ratio)
          + 0.20 * topic_diversity
          + 0.15 * (1 - gini)
          + 0.15 * topic_count_score
        """
        num_topics = metrics.get("num_topics", 0)
        outlier_ratio = metrics.get("outlier_ratio", 1.0)
        diversity = metrics.get("topic_diversity", 0.0)
        gini = metrics.get("topic_size_gini", 1.0)
        silhouette = metrics.get("silhouette_score", 0.0)

        # normalize silhouette from [-1, 1] to [0, 1]
        silhouette_norm = max(0, (silhouette + 1) / 2)

        # topic count score
        if 5 <= num_topics <= 25:
            topic_score = 1.0
        elif 3 <= num_topics < 5 or 25 < num_topics <= 40:
            topic_score = 0.6
        else:
            topic_score = 0.2

        outlier_score = max(0, 1.0 - outlier_ratio)
        balance_score = max(0, 1.0 - gini)

        composite = (
            silhouette_norm * 0.25
            + outlier_score * 0.25
            + diversity * 0.20
            + balance_score * 0.15
            + topic_score * 0.15
        )
        return round(composite, 4)

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
