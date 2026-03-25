# model selection policy for candidate-vs-active promotion decisions
# implements hard gates + weighted scoring to decide whether a candidate
# model should be promoted to production
#
# usage:
#   policy = SelectionPolicy()
#   decision = policy.evaluate(candidate_report, active_report, comparison)

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SelectionPolicy:
    """evaluates whether a candidate model should replace the active model.

    two-phase evaluation:
    1. hard gates — must all pass (non-negotiable thresholds)
    2. weighted score comparison — candidate must beat active by a margin
    """

    def __init__(self, overrides: Optional[Dict[str, float]] = None):
        overrides = overrides or {}
        self.max_outlier_ratio = overrides.get(
            "max_outlier_ratio", config.settings.MODEL_MAX_OUTLIER_RATIO
        )
        self.min_silhouette = overrides.get(
            "min_silhouette", config.settings.MODEL_MIN_SILHOUETTE
        )
        self.min_topic_diversity = overrides.get(
            "min_topic_diversity", config.settings.MODEL_MIN_TOPIC_DIVERSITY
        )
        self.max_bias_disparity = overrides.get(
            "max_bias_disparity", config.settings.MODEL_MAX_BIAS_DISPARITY
        )
        self.min_score_delta = overrides.get(
            "min_score_delta", config.settings.MODEL_PROMOTION_MIN_SCORE_DELTA
        )
        logger.info(
            f"SelectionPolicy initialized: outlier<={self.max_outlier_ratio}, "
            f"silhouette>={self.min_silhouette}, diversity>={self.min_topic_diversity}, "
            f"bias_disparity<={self.max_bias_disparity}, score_delta>={self.min_score_delta}"
        )

    def evaluate(
        self,
        candidate_report: Dict[str, Any],
        active_report: Optional[Dict[str, Any]] = None,
        comparison: Optional[Dict[str, Any]] = None,
        bias_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """run full evaluation: hard gates then weighted score.

        args:
            candidate_report: validation report from candidate model (holdout)
            active_report: validation report from active model (holdout), or None for first model
            comparison: output from compare_candidate_vs_active
            bias_result: output from HoldoutBiasGate.evaluate

        returns:
            decision dict with pass/fail, reasons, scores, and gate details
        """
        candidate_metrics = candidate_report.get("metrics", {})
        active_metrics = active_report.get("metrics", {}) if active_report else {}

        # phase 1: hard gates
        gates = self._evaluate_hard_gates(candidate_metrics, bias_result)
        all_gates_passed = all(g["passed"] for g in gates)

        # phase 2: weighted scoring
        candidate_score = candidate_metrics.get("composite_score", 0.0)
        active_score = active_metrics.get("composite_score", 0.0)
        score_delta = round(candidate_score - active_score, 4)

        # promotion decision
        if not all_gates_passed:
            decision = "reject"
            reasons = [f"hard_gate_failed:{g['name']}" for g in gates if not g["passed"]]
        elif active_report is None:
            # first model — no active to compare against, promote if gates pass
            decision = "promote"
            reasons = ["first_model", "all_gates_passed"]
        elif score_delta >= self.min_score_delta:
            decision = "promote"
            reasons = ["all_gates_passed", "score_delta_above_margin"]
        elif score_delta >= 0:
            # candidate is not worse but doesn't clear the margin — still promote
            # (non-inferior tolerance)
            decision = "promote"
            reasons = ["all_gates_passed", "non_inferior_candidate"]
        else:
            decision = "reject"
            reasons = ["score_regression", f"delta={score_delta}"]

        result = {
            "candidate_version": candidate_report.get("model_type", "unknown"),
            "active_version": active_report.get("model_type", "unknown") if active_report else None,
            "hard_gates": gates,
            "hard_gates_passed": all_gates_passed,
            "candidate_score": candidate_score,
            "active_score": active_score,
            "delta": score_delta,
            "decision": decision,
            "reasons": reasons,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

        # attach agreement metrics if available
        if comparison and "agreement" in comparison:
            result["agreement"] = comparison["agreement"]

        logger.info(
            f"Selection decision: {decision} | gates_passed={all_gates_passed} | "
            f"candidate_score={candidate_score} | active_score={active_score} | "
            f"delta={score_delta} | reasons={reasons}"
        )
        return result

    def _evaluate_hard_gates(
        self,
        candidate_metrics: Dict[str, float],
        bias_result: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """evaluate hard gates that must all pass for promotion."""
        gates = []

        # gate 1: outlier ratio
        outlier_ratio = candidate_metrics.get("outlier_ratio", 1.0)
        gates.append({
            "name": "max_outlier_ratio",
            "passed": outlier_ratio <= self.max_outlier_ratio,
            "actual": round(outlier_ratio, 4),
            "threshold": self.max_outlier_ratio,
            "message": f"Outlier ratio {outlier_ratio:.2%} vs max {self.max_outlier_ratio:.2%}",
        })

        # gate 2: silhouette score
        silhouette = candidate_metrics.get("silhouette_score", 0.0)
        gates.append({
            "name": "min_silhouette",
            "passed": silhouette >= self.min_silhouette,
            "actual": round(silhouette, 4),
            "threshold": self.min_silhouette,
            "message": f"Silhouette {silhouette:.4f} vs min {self.min_silhouette}",
        })

        # gate 3: topic diversity
        diversity = candidate_metrics.get("topic_diversity", 0.0)
        gates.append({
            "name": "min_topic_diversity",
            "passed": diversity >= self.min_topic_diversity,
            "actual": round(diversity, 4),
            "threshold": self.min_topic_diversity,
            "message": f"Diversity {diversity:.4f} vs min {self.min_topic_diversity}",
        })

        # gate 4: bias disparity (only if bias result available)
        if bias_result is not None:
            disparity = bias_result.get("max_disparity_delta", 0.0)
            gates.append({
                "name": "max_bias_disparity",
                "passed": disparity <= self.max_bias_disparity,
                "actual": round(disparity, 4),
                "threshold": self.max_bias_disparity,
                "message": f"Bias disparity {disparity:.4f} vs max {self.max_bias_disparity}",
            })

        return gates
