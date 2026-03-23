# tests for experiment tracker registry operations (Vertex AI) and smoke test
# vertex ai and mlflow calls are mocked

import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))

# inject mock google.cloud.aiplatform into sys.modules so @patch can resolve it
# even when google-cloud-aiplatform is not installed locally
_mock_aiplatform = MagicMock()
if "google.cloud.aiplatform" not in sys.modules:
    import google.cloud  # namespace package — already available via other google packages
    google.cloud.aiplatform = _mock_aiplatform
    sys.modules["google.cloud.aiplatform"] = _mock_aiplatform


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
        mock_settings.GCP_PROJECT_ID = "test-project"
        mock_settings.GCP_REGION = "us-central1"
        yield mock_settings


@pytest.fixture
def mock_config_no_gcp():
    with patch("config.settings") as mock_settings:
        mock_settings.MLFLOW_TRACKING_URI = "sqlite:///test_mlflow.db"
        mock_settings.MLFLOW_ARTIFACT_ROOT = ""
        mock_settings.PROJECT_ROOT = Path("/tmp/test")
        mock_settings.GCP_PROJECT_ID = ""
        mock_settings.GCP_REGION = "us-central1"
        yield mock_settings


class TestExperimentTrackerRegistry:
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_registry_enabled_with_gcp_project(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        tracker = ExperimentTracker("test")
        assert tracker.registry_enabled is True
        mock_ai_init.assert_called_once_with(project="test-project", location="us-central1")

    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_registry_disabled_without_gcp_project(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_config_no_gcp):
        from topic_modeling.experiment_tracker import ExperimentTracker
        tracker = ExperimentTracker("test")
        assert tracker.registry_enabled is False

    @patch("google.cloud.aiplatform.Model.upload")
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_register_model(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_upload, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_model = Mock()
        mock_model.resource_name = "projects/test-project/locations/us-central1/models/12345"
        mock_upload.return_value = mock_model

        tracker = ExperimentTracker("test")
        result = tracker.register_model(
            "bertopic_journals",
            artifact_uri="gs://bucket/models/journals/promoted/run-123",
            run_id="run-123",
        )
        assert result == "projects/test-project/locations/us-central1/models/12345"
        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["display_name"] == "bertopic_journals"
        assert call_kwargs["artifact_uri"] == "gs://bucket/models/journals/promoted/run-123"
        assert call_kwargs["labels"]["mlflow_run_id"] == "run_123"
        assert call_kwargs["labels"]["pipeline"] == "calmai"

    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_register_model_no_artifact_uri(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker
        tracker = ExperimentTracker("test")
        result = tracker.register_model("bertopic_journals")
        assert result is None

    @patch("google.cloud.aiplatform.Model")
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_promote_to_production(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_model_cls, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_model = MagicMock()
        mock_model.labels = {"pipeline": "calmai"}
        mock_model_cls.return_value = mock_model

        tracker = ExperimentTracker("test")
        result = tracker.promote_to_production(
            "bertopic_journals",
            "projects/test-project/locations/us-central1/models/12345",
        )
        assert result is True
        mock_model.update.assert_called_once()
        update_kwargs = mock_model.update.call_args[1]
        assert update_kwargs["labels"]["status"] == "production"
        assert update_kwargs["labels"]["pipeline"] == "calmai"

    @patch("google.cloud.aiplatform.Model.list")
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_production_version(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_list, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_model = Mock()
        mock_model.resource_name = "projects/test-project/locations/us-central1/models/12345"
        mock_model.display_name = "bertopic_journals"
        mock_model.artifact_uri = "gs://bucket/models/journals/promoted/run-123"
        mock_model.labels = {"status": "production", "pipeline": "calmai"}
        mock_model.create_time = "2025-01-01T00:00:00Z"
        mock_list.return_value = [mock_model]

        tracker = ExperimentTracker("test")
        prod = tracker.get_production_version("bertopic_journals")

        assert prod is not None
        assert prod["resource_name"] == "projects/test-project/locations/us-central1/models/12345"
        assert prod["display_name"] == "bertopic_journals"
        assert prod["artifact_uri"] == "gs://bucket/models/journals/promoted/run-123"
        assert prod["labels"]["status"] == "production"

    @patch("google.cloud.aiplatform.Model.list")
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_production_version_none(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_list, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_list.return_value = []
        tracker = ExperimentTracker("test")
        assert tracker.get_production_version("bertopic_journals") is None

    @patch("google.cloud.aiplatform.Model.list")
    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_archived_versions(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_list, mock_config_settings):
        from topic_modeling.experiment_tracker import ExperimentTracker

        mock_v1 = Mock()
        mock_v1.resource_name = "projects/test-project/locations/us-central1/models/111"
        mock_v1.artifact_uri = "gs://bucket/models/journals/v1"
        mock_v1.labels = {"status": "production"}
        mock_v1.create_time = "2025-01-02T00:00:00Z"

        mock_v2 = Mock()
        mock_v2.resource_name = "projects/test-project/locations/us-central1/models/222"
        mock_v2.artifact_uri = "gs://bucket/models/journals/v2"
        mock_v2.labels = {"status": "archived"}
        mock_v2.create_time = "2025-01-01T00:00:00Z"

        mock_list.return_value = [mock_v1, mock_v2]

        tracker = ExperimentTracker("test")
        archived = tracker.get_archived_versions("bertopic_journals")
        assert len(archived) == 2
        assert archived[0]["resource_name"].endswith("/111")
        assert archived[1]["resource_name"].endswith("/222")

    @patch("google.cloud.aiplatform.init")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_promote_not_enabled(self, mock_set_exp, mock_set_uri, mock_ai_init, mock_config_no_gcp):
        from topic_modeling.experiment_tracker import ExperimentTracker
        tracker = ExperimentTracker("test")
        result = tracker.promote_to_production("bertopic_journals", "some/resource")
        assert result is False


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
