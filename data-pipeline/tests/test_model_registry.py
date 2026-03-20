# tests for experiment tracker registry operations and rollback
# all mlflow calls are mocked

import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))


@pytest.fixture
def mock_config_settings():
    with patch("config.settings") as mock_settings:
        mock_settings.MLFLOW_TRACKING_URI = "sqlite:///test_mlflow.db"
        mock_settings.MLFLOW_ARTIFACT_ROOT = ""
        mock_settings.PROJECT_ROOT = Path("/tmp/test")
        mock_settings.MODEL_MAX_OUTLIER_RATIO = 0.20
        mock_settings.MODEL_MIN_SILHOUETTE = 0.10
        mock_settings.MODEL_MIN_TOPIC_DIVERSITY = 0.50
        mock_settings.MODEL_MAX_BIAS_DISPARITY = 0.10
        mock_settings.MODEL_PROMOTION_MIN_SCORE_DELTA = 0.01
        yield mock_settings


class TestExperimentTrackerRegistry:
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_registry_enabled_with_tracking_uri(self, mock_set_exp, mock_set_uri, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        tracker = ExperimentTracker("test")
        assert tracker.registry_enabled is True
        mock_set_uri.assert_called_with("sqlite:///test_mlflow.db")

    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_registry_disabled_without_tracking_uri(self, mock_set_exp, mock_set_uri):
        with patch("config.settings") as mock_settings:
            mock_settings.MLFLOW_TRACKING_URI = ""
            mock_settings.MLFLOW_ARTIFACT_ROOT = ""
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            assert tracker.registry_enabled is False

    @patch("mlflow.register_model")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_register_model(self, mock_set_exp, mock_set_uri, mock_register, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_result = Mock()
        mock_result.version = "1"
        mock_register.return_value = mock_result

        tracker = ExperimentTracker("test")
        tracker._run_id = "run-123"

        version = tracker.register_model("bertopic_journals")
        assert version == "1"
        mock_register.assert_called_once_with("runs:/run-123/model", "bertopic_journals")

    @patch("mlflow.register_model")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_register_model_no_run_id(self, mock_set_exp, mock_set_uri, mock_register, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        tracker = ExperimentTracker("test")
        tracker._run_id = None

        version = tracker.register_model("bertopic_journals")
        assert version is None
        mock_register.assert_not_called()

    @patch("mlflow.MlflowClient")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_transition_model_stage(self, mock_set_exp, mock_set_uri, mock_client_cls, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        tracker = ExperimentTracker("test")
        result = tracker.transition_model_stage("bertopic_journals", "1", "Production")

        assert result is True
        mock_client.transition_model_version_stage.assert_called_once_with(
            name="bertopic_journals",
            version="1",
            stage="Production",
            archive_existing_versions=True,
        )

    @patch("mlflow.MlflowClient")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_production_version(self, mock_set_exp, mock_set_uri, mock_client_cls, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_version = Mock()
        mock_version.version = "3"
        mock_version.run_id = "run-xyz"
        mock_version.source = "runs:/run-xyz/model"
        mock_version.current_stage = "Production"
        mock_version.description = "latest"

        mock_client = MagicMock()
        mock_client.get_latest_versions.return_value = [mock_version]
        mock_client_cls.return_value = mock_client

        tracker = ExperimentTracker("test")
        prod = tracker.get_production_version("bertopic_journals")

        assert prod is not None
        assert prod["version"] == "3"
        assert prod["run_id"] == "run-xyz"

    @patch("mlflow.MlflowClient")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_production_version_none(self, mock_set_exp, mock_set_uri, mock_client_cls, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_client = MagicMock()
        mock_client.get_latest_versions.return_value = []
        mock_client_cls.return_value = mock_client

        tracker = ExperimentTracker("test")
        assert tracker.get_production_version("bertopic_journals") is None

    @patch("mlflow.MlflowClient")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_archived_versions(self, mock_set_exp, mock_set_uri, mock_client_cls, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_v1 = Mock()
        mock_v1.version = "1"
        mock_v1.run_id = "run-1"
        mock_v1.source = "runs:/run-1/model"
        mock_v1.current_stage = "Archived"

        mock_v2 = Mock()
        mock_v2.version = "2"
        mock_v2.run_id = "run-2"
        mock_v2.source = "runs:/run-2/model"
        mock_v2.current_stage = "Archived"

        mock_client = MagicMock()
        mock_client.get_latest_versions.return_value = [mock_v1, mock_v2]
        mock_client_cls.return_value = mock_client

        tracker = ExperimentTracker("test")
        archived = tracker.get_archived_versions("bertopic_journals")
        assert len(archived) == 2
        assert archived[0]["version"] == "1"


class TestModelRollback:
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_rollback_success(self, mock_set_exp, mock_set_uri, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        from topic_modeling.rollback import ModelRollback

        tracker = ExperimentTracker("test")

        # mock production and archived versions
        tracker.get_production_version = Mock(return_value={
            "version": "3", "run_id": "run-3", "source": "s", "stage": "Production", "description": "",
        })
        tracker.get_archived_versions = Mock(return_value=[
            {"version": "2", "run_id": "run-2", "source": "s", "stage": "Archived"},
        ])
        tracker.transition_model_stage = Mock(return_value=True)

        rollback = ModelRollback(tracker)
        result = rollback.rollback("bertopic_journals", reason="smoke_test_failed")

        assert result["success"] is True
        assert result["rolled_back_from"] == "3"
        assert result["rolled_back_to"] == "2"
        assert tracker.transition_model_stage.call_count == 2

    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_rollback_no_production(self, mock_set_exp, mock_set_uri, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        from topic_modeling.rollback import ModelRollback

        tracker = ExperimentTracker("test")
        tracker.get_production_version = Mock(return_value=None)

        rollback = ModelRollback(tracker)
        result = rollback.rollback("bertopic_journals")
        assert result["success"] is False
        assert result["error"] == "no_production_version"

    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_rollback_no_archived(self, mock_set_exp, mock_set_uri, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        from topic_modeling.rollback import ModelRollback

        tracker = ExperimentTracker("test")
        tracker.get_production_version = Mock(return_value={
            "version": "3", "run_id": "run-3", "source": "s", "stage": "Production", "description": "",
        })
        tracker.get_archived_versions = Mock(return_value=[])

        rollback = ModelRollback(tracker)
        result = rollback.rollback("bertopic_journals")
        assert result["success"] is False
        assert result["error"] == "no_archived_version"

    def test_rollback_no_registry(self):
        from topic_modeling.rollback import ModelRollback

        rollback = ModelRollback(tracker=None)
        result = rollback.rollback("bertopic_journals")
        assert result["success"] is False
        assert result["error"] == "registry_not_enabled"


class TestSmokeTest:
    @patch("bertopic.BERTopic")
    def test_smoke_test_passes(self, mock_bt):
        from topic_modeling.rollback import smoke_test_model

        mock_model = MagicMock()
        mock_model.transform.return_value = ([0, 1, 2], None)
        mock_bt.load.return_value = mock_model

        result = smoke_test_model("test_model", "/path/to/model", ["doc1", "doc2", "doc3"])
        assert result["passed"] is True
        assert result["num_docs"] == 3

    @patch("bertopic.BERTopic")
    def test_smoke_test_load_failure(self, mock_bt):
        from topic_modeling.rollback import smoke_test_model

        mock_bt.load.side_effect = Exception("file not found")
        result = smoke_test_model("test_model", "/bad/path", ["doc1"])
        assert result["passed"] is False
        assert "load_failed" in result["error"]

    @patch("bertopic.BERTopic")
    def test_smoke_test_inference_failure(self, mock_bt):
        from topic_modeling.rollback import smoke_test_model

        mock_model = MagicMock()
        mock_model.transform.side_effect = Exception("transform error")
        mock_bt.load.return_value = mock_model

        result = smoke_test_model("test_model", "/path", ["doc1"])
        assert result["passed"] is False
        assert "inference_failed" in result["error"]

    @patch("bertopic.BERTopic")
    def test_smoke_test_no_docs(self, mock_bt):
        from topic_modeling.rollback import smoke_test_model

        mock_bt.load.return_value = MagicMock()
        result = smoke_test_model("test_model", "/path", [])
        assert result["passed"] is True
        assert "warning" in result
