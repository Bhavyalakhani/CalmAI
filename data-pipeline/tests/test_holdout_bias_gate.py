# tests for holdout bias gate
# covers per-slice metrics, disparity calculation, and gate pass/fail logic

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))


@pytest.fixture
def mock_config_settings():
    with patch("config.settings") as mock_settings:
        mock_settings.MODEL_MAX_BIAS_DISPARITY = 0.10
        yield mock_settings


@pytest.fixture
def holdout_df():
    """holdout dataframe with sliceable columns."""
    return pd.DataFrame({
        "content": [f"doc {i}" for i in range(20)],
        "day_of_week": [0, 1, 2, 3, 4, 5, 6] * 2 + [0, 1, 2, 3, 4, 5],
        "month": [1] * 10 + [2] * 10,
        "severity": ["mild"] * 8 + ["moderate"] * 8 + ["severe"] * 4,
    })


class TestHoldoutBiasGate:
    def test_gate_passes_no_disparity(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        topics = list(range(5)) * 4  # 20 docs, 5 topics, balanced
        result = gate.evaluate(
            holdout_df=holdout_df,
            candidate_topics=topics,
            candidate_probs=None,
            num_topics=5,
            slice_columns=["month"],
        )
        assert result["passed"] is True
        assert result["max_disparity_delta"] == 0.0

    def test_gate_fails_high_slice_outlier(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate(max_slice_outlier=0.25)
        # make month=2 slice all outliers
        topics = [0, 1, 2, 3, 4, 0, 1, 2, 3, 4] + [-1] * 10
        result = gate.evaluate(
            holdout_df=holdout_df,
            candidate_topics=topics,
            candidate_probs=None,
            num_topics=5,
            slice_columns=["month"],
        )
        assert result["passed"] is False
        assert len(result["gate_failures"]) > 0

    def test_gate_fails_high_disparity(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate(max_disparity=0.05)

        # candidate: balanced
        candidate_topics = list(range(5)) * 4

        # active: month=2 slice has all outliers (big disparity)
        active_topics = [0, 1, 2, 3, 4, 0, 1, 2, 3, 4] + [-1] * 10

        result = gate.evaluate(
            holdout_df=holdout_df,
            candidate_topics=candidate_topics,
            candidate_probs=None,
            active_topics=active_topics,
            active_probs=None,
            num_topics=5,
            slice_columns=["month"],
        )
        assert result["max_disparity_delta"] > 0.05
        assert result["passed"] is False

    def test_auto_detect_slice_columns(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        detected = HoldoutBiasGate._detect_slice_columns(holdout_df)
        # day_of_week has 7 values, month has 2, severity has 3
        assert "month" in detected
        assert "severity" in detected
        assert "day_of_week" in detected

    def test_compute_slice_metrics(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        df = holdout_df.copy()
        df["_candidate_topic"] = [0, 1, -1, 2, 0, 1, -1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2]
        df["_candidate_confidence"] = [0.8] * 20

        metrics = gate._compute_slice_metrics(df, "_candidate_topic", "_candidate_confidence", num_topics=3)
        assert "outlier_ratio" in metrics
        assert "topic_coverage" in metrics
        assert "confidence_proxy" in metrics
        assert 0 <= metrics["outlier_ratio"] <= 1
        assert 0 <= metrics["topic_coverage"] <= 1

    def test_empty_slice_skipped(self, mock_config_settings):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        df = pd.DataFrame({
            "content": ["doc1"],
            "category": ["A"],
        })
        result = gate.evaluate(
            holdout_df=df,
            candidate_topics=[0],
            candidate_probs=None,
            num_topics=1,
            slice_columns=["category"],
        )
        # single-element slice should be skipped (< 2)
        assert result["passed"] is True

    def test_with_probability_matrix(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        topics = list(range(5)) * 4
        probs = np.random.rand(20, 5).astype(np.float32)

        result = gate.evaluate(
            holdout_df=holdout_df,
            candidate_topics=topics,
            candidate_probs=probs,
            num_topics=5,
            slice_columns=["month"],
        )
        assert result["passed"] is True
        # confidence_proxy should be computed from probs
        for col_results in result["slice_results"].values():
            for slice_data in col_results.values():
                assert slice_data["candidate"]["confidence_proxy"] > 0

    def test_missing_slice_column_ignored(self, mock_config_settings, holdout_df):
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        topics = list(range(5)) * 4
        result = gate.evaluate(
            holdout_df=holdout_df,
            candidate_topics=topics,
            candidate_probs=None,
            num_topics=5,
            slice_columns=["nonexistent_column"],
        )
        assert result["passed"] is True
        assert result["slice_results"] == {}
