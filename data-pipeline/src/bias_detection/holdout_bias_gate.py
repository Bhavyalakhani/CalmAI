# holdout bias gate for model promotion decisions
# computes per-slice metrics on holdout predictions and checks for
# disparities between candidate and active models
#
# this is a GATE (blocks promotion) — distinct from the existing
# descriptive bias analyzers which run post-hoc for observability

import logging
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .slicer import DataSlicer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HoldoutBiasGate:
    """evaluates bias on holdout predictions to gate model promotion.

    for each slice:
      - outlier_ratio: fraction of docs assigned to topic -1
      - topic_coverage: fraction of non-outlier topics that appear in the slice
      - confidence_proxy: mean max probability across docs in the slice

    disparity_delta = max |candidate_metric[slice] - active_metric[slice]|
    across all slices and all metrics.

    gate fails if:
      - any slice outlier_ratio > max_slice_outlier (default 0.25)
      - disparity_delta > max_disparity (from config)
    """

    def __init__(
        self,
        max_slice_outlier: float = 0.25,
        max_disparity: Optional[float] = None,
    ):
        self.max_slice_outlier = max_slice_outlier
        self.max_disparity = max_disparity or config.settings.MODEL_MAX_BIAS_DISPARITY
        logger.info(
            f"HoldoutBiasGate: max_slice_outlier={self.max_slice_outlier}, "
            f"max_disparity={self.max_disparity}"
        )

    def evaluate(
        self,
        holdout_df: pd.DataFrame,
        candidate_topics: List[int],
        candidate_probs: Optional[np.ndarray],
        active_topics: Optional[List[int]] = None,
        active_probs: Optional[np.ndarray] = None,
        slice_columns: Optional[List[str]] = None,
        num_topics: int = 0,
    ) -> Dict[str, Any]:
        """run bias gate on holdout predictions.

        args:
            holdout_df: holdout dataframe with metadata columns for slicing
            candidate_topics: topic assignments from candidate model
            candidate_probs: probability matrix from candidate model
            active_topics: topic assignments from active model (None for first model)
            active_probs: probability matrix from active model
            slice_columns: columns to slice by (auto-detected if None)
            num_topics: total number of topics in candidate model

        returns:
            gate result dict with pass/fail, per-slice metrics, and disparity
        """
        logger.info(f"Running holdout bias gate on {len(holdout_df)} documents")

        # auto-detect slice columns
        if slice_columns is None:
            slice_columns = self._detect_slice_columns(holdout_df)
            logger.info(f"Auto-detected slice columns: {slice_columns}")

        # add predictions to df for slicing
        df = holdout_df.copy()
        df["_candidate_topic"] = candidate_topics

        if candidate_probs is not None and len(candidate_probs.shape) > 1:
            df["_candidate_confidence"] = np.max(candidate_probs, axis=1)
        else:
            df["_candidate_confidence"] = 0.0

        if active_topics is not None:
            df["_active_topic"] = active_topics
            if active_probs is not None and len(active_probs.shape) > 1:
                df["_active_confidence"] = np.max(active_probs, axis=1)
            else:
                df["_active_confidence"] = 0.0

        # compute per-slice metrics for each slice column
        all_slice_results = {}
        max_disparity_delta = 0.0
        gate_failures = []

        for col in slice_columns:
            if col not in df.columns:
                logger.warning(f"Slice column '{col}' not in holdout_df — skipping")
                continue

            slicer = DataSlicer(df)
            slices = slicer.slice_by_category(col)

            if not slices:
                continue

            col_results = {}
            for slice_name, slice_df in slices.items():
                if len(slice_df) < 2:
                    continue

                candidate_slice_metrics = self._compute_slice_metrics(
                    slice_df, "_candidate_topic", "_candidate_confidence", num_topics
                )
                col_results[slice_name] = {
                    "count": len(slice_df),
                    "candidate": candidate_slice_metrics,
                }

                # check slice outlier gate
                if candidate_slice_metrics["outlier_ratio"] > self.max_slice_outlier:
                    gate_failures.append(
                        f"{col}:{slice_name} outlier_ratio="
                        f"{candidate_slice_metrics['outlier_ratio']:.2%}"
                    )

                # compute disparity if active predictions available
                if active_topics is not None:
                    active_slice_metrics = self._compute_slice_metrics(
                        slice_df, "_active_topic", "_active_confidence", num_topics
                    )
                    col_results[slice_name]["active"] = active_slice_metrics

                    # disparity delta across all metrics
                    for metric_key in ["outlier_ratio", "topic_coverage", "confidence_proxy"]:
                        c_val = candidate_slice_metrics.get(metric_key, 0)
                        a_val = active_slice_metrics.get(metric_key, 0)
                        delta = abs(c_val - a_val)
                        max_disparity_delta = max(max_disparity_delta, delta)

            all_slice_results[col] = col_results

        # check disparity gate
        if max_disparity_delta > self.max_disparity:
            gate_failures.append(
                f"max_disparity_delta={max_disparity_delta:.4f} > {self.max_disparity}"
            )

        passed = len(gate_failures) == 0

        result = {
            "passed": passed,
            "max_disparity_delta": round(max_disparity_delta, 4),
            "gate_failures": gate_failures,
            "slice_results": all_slice_results,
            "slice_columns_used": slice_columns,
            "max_slice_outlier_threshold": self.max_slice_outlier,
            "max_disparity_threshold": self.max_disparity,
        }

        if passed:
            logger.info(f"Bias gate PASSED: max_disparity={max_disparity_delta:.4f}")
        else:
            logger.warning(
                f"Bias gate FAILED: {len(gate_failures)} failures — {gate_failures}"
            )

        return result

    def _compute_slice_metrics(
        self,
        slice_df: pd.DataFrame,
        topic_col: str,
        confidence_col: str,
        num_topics: int,
    ) -> Dict[str, float]:
        """compute per-slice bias metrics."""
        topics = slice_df[topic_col].values
        n = len(topics)

        # outlier ratio
        outlier_count = int((topics == -1).sum())
        outlier_ratio = outlier_count / n if n > 0 else 0.0

        # topic coverage (fraction of non-outlier topics present in this slice)
        unique_topics = set(topics[topics != -1])
        topic_coverage = len(unique_topics) / num_topics if num_topics > 0 else 0.0

        # confidence proxy (mean max probability)
        confidence_proxy = 0.0
        if confidence_col in slice_df.columns:
            confidence_proxy = float(slice_df[confidence_col].mean())

        return {
            "outlier_ratio": round(outlier_ratio, 4),
            "topic_coverage": round(topic_coverage, 4),
            "confidence_proxy": round(confidence_proxy, 4),
        }

    @staticmethod
    def _detect_slice_columns(df: pd.DataFrame) -> List[str]:
        """auto-detect reasonable slice columns from the dataframe."""
        candidates = []

        # common metadata columns
        known_slice_cols = [
            "day_of_week", "month", "severity", "patient_id",
            "source_file", "year",
        ]
        for col in known_slice_cols:
            if col in df.columns:
                n_unique = df[col].nunique()
                # only slice on columns with 2-20 unique values
                if 2 <= n_unique <= 20:
                    candidates.append(col)

        return candidates if candidates else []
