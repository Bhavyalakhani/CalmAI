# tests for model selection policy
# covers hard gates, scoring, and decision outcomes

import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))


@pytest.fixture
def mock_config_settings():
    with patch("config.settings") as mock_settings:
        mock_settings.MODEL_MAX_OUTLIER_RATIO = 0.20
        mock_settings.MODEL_MIN_SILHOUETTE = 0.10
        mock_settings.MODEL_MIN_TOPIC_DIVERSITY = 0.50
        mock_settings.MODEL_MAX_BIAS_DISPARITY = 0.10
        mock_settings.MODEL_PROMOTION_MIN_SCORE_DELTA = 0.01
        yield mock_settings


class TestSelectionPolicy:
    def test_all_gates_pass_first_model(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert decision["decision"] == "promote"
        assert decision["hard_gates_passed"] is True
        assert "first_model" in decision["reasons"]

    def test_outlier_gate_fails(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.30,  # exceeds 0.20 threshold
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert decision["decision"] == "reject"
        assert not decision["hard_gates_passed"]
        assert any("max_outlier_ratio" in r for r in decision["reasons"])

    def test_silhouette_gate_fails(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.05,  # below 0.10 threshold
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert decision["decision"] == "reject"
        assert any("min_silhouette" in r for r in decision["reasons"])

    def test_diversity_gate_fails(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.30,  # below 0.50 threshold
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert decision["decision"] == "reject"

    def test_bias_gate_fails(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        bias_result = {"max_disparity_delta": 0.15}  # exceeds 0.10 threshold
        decision = policy.evaluate(candidate, active_report=None, bias_result=bias_result)
        assert decision["decision"] == "reject"
        assert any("max_bias_disparity" in r for r in decision["reasons"])

    def test_promote_over_active(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        active = {
            "metrics": {
                "composite_score": 0.60,
            }
        }
        decision = policy.evaluate(candidate, active_report=active)
        assert decision["decision"] == "promote"
        assert decision["delta"] == 0.05

    def test_reject_score_regression(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.50,
            }
        }
        active = {
            "metrics": {
                "composite_score": 0.60,
            }
        }
        decision = policy.evaluate(candidate, active_report=active)
        assert decision["decision"] == "reject"
        assert "score_regression" in decision["reasons"]

    def test_non_inferior_tolerance(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.605,  # equal to active + 0.005 (< margin but >= 0)
            }
        }
        active = {
            "metrics": {
                "composite_score": 0.60,
            }
        }
        decision = policy.evaluate(candidate, active_report=active)
        assert decision["decision"] == "promote"
        assert "non_inferior_candidate" in decision["reasons"]

    def test_custom_overrides(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy(overrides={"max_outlier_ratio": 0.50})
        candidate = {
            "metrics": {
                "outlier_ratio": 0.30,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert decision["decision"] == "promote"

    def test_decision_includes_agreement(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        comparison = {"agreement": {"nmi": 0.85, "ari": 0.72, "v_measure": 0.80}}
        decision = policy.evaluate(candidate, active_report=None, comparison=comparison)
        assert "agreement" in decision
        assert decision["agreement"]["nmi"] == 0.85

    def test_gate_details_in_result(self, mock_config_settings):
        from topic_modeling.selection_policy import SelectionPolicy

        policy = SelectionPolicy()
        candidate = {
            "metrics": {
                "outlier_ratio": 0.05,
                "silhouette_score": 0.25,
                "topic_diversity": 0.70,
                "composite_score": 0.65,
            }
        }
        decision = policy.evaluate(candidate, active_report=None)
        assert "hard_gates" in decision
        assert len(decision["hard_gates"]) == 3  # no bias gate when bias_result is None
        for gate in decision["hard_gates"]:
            assert "name" in gate
            assert "passed" in gate
            assert "actual" in gate
            assert "threshold" in gate
