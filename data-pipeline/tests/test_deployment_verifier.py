# tests for the post-deployment verification module
# verifies model load, inference, topic quality, and latency checks

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))

from monitoring.deployment_verifier import verify_deployed_model, VERIFICATION_DOCS


class TestVerifyDeployedModel:
    @patch("bertopic.BERTopic")
    def test_all_checks_pass(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path/to/model")
        assert result["passed"] is True
        assert result["checks"]["load"]["passed"] is True
        assert result["checks"]["inference"]["passed"] is True
        assert result["checks"]["topic_quality"]["passed"] is True
        assert result["checks"]["latency"]["passed"] is True

    @patch("bertopic.BERTopic")
    def test_model_load_failure(self, mock_bt):
        mock_bt.load.side_effect = Exception("file not found")
        result = verify_deployed_model("journals", "/bad/path")
        assert result["passed"] is False
        assert result["checks"]["load"]["passed"] is False
        assert "load_failed" in result["checks"]["load"]["error"]

    @patch("bertopic.BERTopic")
    def test_inference_failure(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.side_effect = Exception("transform error")
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path")
        assert result["passed"] is False
        assert result["checks"]["inference"]["passed"] is False
        assert "inference_failed" in result["checks"]["inference"]["error"]

    @patch("bertopic.BERTopic")
    def test_all_outlier_topics_fails(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([-1, -1, -1, -1, -1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path")
        assert result["passed"] is False
        assert result["checks"]["topic_quality"]["passed"] is False
        assert result["checks"]["topic_quality"]["all_outlier"] is True

    @patch("bertopic.BERTopic")
    def test_custom_test_docs(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1], None)
        mock_bt.load.return_value = mock_model

        custom_docs = ["doc one", "doc two"]
        result = verify_deployed_model("journals", "/path", test_docs=custom_docs)
        assert result["passed"] is True
        assert result["checks"]["inference"]["num_docs"] == 2

    @patch("bertopic.BERTopic")
    def test_model_type_in_report(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("conversations", "/path")
        assert result["model_type"] == "conversations"

    @patch("bertopic.BERTopic")
    def test_model_dir_in_report(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/custom/path")
        assert result["model_dir"] == "/custom/path"

    @patch("bertopic.BERTopic")
    def test_load_time_reported(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path")
        assert "load_time_ms" in result["checks"]["load"]
        assert result["checks"]["load"]["load_time_ms"] >= 0

    @patch("bertopic.BERTopic")
    def test_latency_reported(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path")
        assert "latency_ms" in result["checks"]["latency"]

    @patch("bertopic.BERTopic")
    def test_topics_assigned_count(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 0, 1, 1, 2], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("journals", "/path")
        assert result["checks"]["inference"]["num_topics_assigned"] == 3

    def test_default_verification_docs_exist(self):
        assert len(VERIFICATION_DOCS) >= 3
        for doc in VERIFICATION_DOCS:
            assert isinstance(doc, str)
            assert len(doc) > 10

    @patch("bertopic.BERTopic")
    def test_severity_model_type(self, mock_bt):
        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2, 0, 1], None)
        mock_bt.load.return_value = mock_model

        result = verify_deployed_model("severity", "/path/to/severity")
        assert result["passed"] is True
        assert result["model_type"] == "severity"
