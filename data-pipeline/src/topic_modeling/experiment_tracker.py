# mlflow experiment tracking wrapper + vertex ai model registry
# mlflow: tracks hyperparameters, metrics, and model artifacts per training run
# vertex ai: model versioning and registration in gcp model registry
# the two systems are independent — mlflow for experiment tracking, vertex ai for deployment

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import get_mlruns_dir

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """thin wrapper around mlflow for tracking topic model experiments,
    with vertex ai model registry for cloud-native model versioning.

    mlflow handles experiment tracking (metrics, params, artifacts).
    vertex ai handles model registration and versioning when GCP_PROJECT_ID is set.
    """

    def __init__(self, experiment_name: str = "journal_topic_model"):
        self.experiment_name = experiment_name
        self._run_id: Optional[str] = None
        self._mlflow_available = False
        self._vertex_ai_available = False
        self._setup_tracking()
        self._setup_vertex_ai()

    def _cleanup_sqlite_migration_artifacts(self, tracking_uri: str):
        """drop stale Alembic temp tables left by interrupted MLflow migrations.

        when a migration is killed mid-flight, SQLite retains the temp table
        (e.g. _alembic_tmp_latest_metrics). the next run tries to CREATE it
        again and fails. dropping it here lets the migration resume cleanly.
        """
        if not tracking_uri.startswith("sqlite:///"):
            return
        db_path = tracking_uri[len("sqlite:///"):]
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%'"
            )
            stale = [row[0] for row in cursor.fetchall()]
            for table in stale:
                cursor.execute(f"DROP TABLE IF EXISTS [{table}]")
                logger.warning(f"Dropped stale Alembic temp table: {table}")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not clean up stale Alembic temp tables: {e}")

    def _setup_tracking(self):
        """configure mlflow tracking URI and experiment.

        mlflow is used purely for experiment tracking (metrics, params, artifacts).
        if mlflow is not installed, tracking is silently disabled so training continues.
        """
        try:
            import mlflow
        except ModuleNotFoundError:
            logger.warning(
                "mlflow not installed — experiment tracking disabled. "
                "Install mlflow to enable: pip install mlflow>=3.0.0"
            )
            self._mlflow_available = False
            return

        self._mlflow_available = True

        tracking_uri = config.settings.MLFLOW_TRACKING_URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
            self._cleanup_sqlite_migration_artifacts(tracking_uri)
            logger.info(
                f"MLflow tracking: experiment={self.experiment_name}, "
                f"uri={tracking_uri}"
            )
        else:
            # fallback to local file-backed storage
            mlruns_dir = get_mlruns_dir()
            tracking_uri = mlruns_dir.resolve().as_uri()
            mlflow.set_tracking_uri(tracking_uri)
            logger.warning(
                f"MLFLOW_TRACKING_URI not set — using file-backed storage: "
                f"uri={tracking_uri}"
            )

        # configure artifact root so models are stored in a known location
        artifact_root = config.settings.MLFLOW_ARTIFACT_ROOT
        if artifact_root:
            from pathlib import Path as _Path
            _Path(artifact_root).mkdir(parents=True, exist_ok=True)
            logger.info(f"MLflow artifact root: {artifact_root}")

        try:
            mlflow.set_experiment(self.experiment_name)
        except Exception as e:
            logger.warning(f"Failed to set MLflow experiment '{self.experiment_name}': {e}")

    def _setup_vertex_ai(self):
        """initialize Vertex AI Model Registry if GCP_PROJECT_ID is configured.

        vertex ai is used for cloud-native model versioning and registration.
        disabled gracefully if google-cloud-aiplatform is not installed or
        GCP_PROJECT_ID is not set.
        """
        try:
            from google.cloud import aiplatform  # noqa: F401
        except ImportError:
            logger.info(
                "google-cloud-aiplatform not installed — Vertex AI Model Registry disabled"
            )
            self._vertex_ai_available = False
            return

        gcp_project = config.settings.GCP_PROJECT_ID
        gcp_region = config.settings.GCP_REGION
        if not gcp_project:
            logger.info("GCP_PROJECT_ID not set — Vertex AI Model Registry disabled")
            self._vertex_ai_available = False
            return

        try:
            aiplatform.init(project=gcp_project, location=gcp_region)
            self._vertex_ai_available = True
            logger.info(
                f"Vertex AI Model Registry enabled: project={gcp_project}, region={gcp_region}"
            )
        except Exception as e:
            logger.warning(f"Vertex AI initialization failed: {e}")
            self._vertex_ai_available = False

    @property
    def registry_enabled(self) -> bool:
        return self._vertex_ai_available

    # mlflow experiment tracking methods (unchanged)

    def start_run(self, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        """start a new mlflow run and optionally log parameters"""
        if not self._mlflow_available:
            logger.debug("MLflow not available — skipping start_run")
            return ""
        import mlflow
        run = mlflow.start_run(run_name=run_name)
        self._run_id = run.info.run_id

        if params:
            for key, value in params.items():
                mlflow.log_param(key, value)

        logger.info(f"Started MLflow run: {self._run_id} ({run_name})")
        return self._run_id

    def log_metrics(self, metrics: Dict[str, float]):
        """log metrics to the active run"""
        if not self._mlflow_available:
            return
        import mlflow
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        logger.info(f"Logged metrics: {metrics}")

    def log_params(self, params: Dict[str, Any]):
        """log additional parameters to the active run"""
        if not self._mlflow_available:
            return
        import mlflow
        for key, value in params.items():
            mlflow.log_param(key, str(value))

    def log_artifact(self, path: str):
        """log a file artifact to the active run"""
        if not self._mlflow_available:
            return
        import mlflow
        mlflow.log_artifact(path)
        logger.info(f"Logged artifact: {path}")

    def log_artifacts_dir(self, dir_path: str):
        """log all files in a directory as artifacts"""
        if not self._mlflow_available:
            return
        import mlflow
        mlflow.log_artifacts(dir_path)
        logger.info(f"Logged artifacts directory: {dir_path}")

    def log_model_dir(self, dir_path: str, artifact_path: str = "model"):
        """log a trained model directory as an MLflow pyfunc model.

        stores raw files as artifacts and wraps as pyfunc for mlflow tracking.
        always call this BEFORE end_run() so the active run is still open.

        args:
            dir_path: local path to the model directory
            artifact_path: subdirectory name in the artifact store (default: "model")
        """
        if not self._mlflow_available:
            return
        import mlflow
        from pathlib import Path

        try:
            # log raw files so they're accessible directly
            mlflow.log_artifacts(dir_path, artifact_path=artifact_path)

            class _BERTopicWrapper(mlflow.pyfunc.PythonModel):
                def load_context(self, context):
                    from bertopic import BERTopic
                    self.model = BERTopic.load(context.artifacts["model_dir"])

                def predict(self, context, model_input):
                    docs = model_input.iloc[:, 0].tolist() if hasattr(model_input, "iloc") else list(model_input)
                    topics, _ = self.model.transform(docs)
                    return topics

            mlflow.pyfunc.log_model(
                artifact_path=artifact_path,
                python_model=_BERTopicWrapper(),
                artifacts={"model_dir": str(Path(dir_path).resolve())},
            )
            logger.info(
                f"Logged model artifacts from '{dir_path}' under "
                f"artifact_path='{artifact_path}' in run {self._run_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to log model artifacts to MLflow: {e}")

    def set_tag(self, key: str, value: str):
        """set a tag on the active run"""
        if not self._mlflow_available:
            return
        import mlflow
        mlflow.set_tag(key, value)

    def tag_best_model(self):
        """tag the current run as the best/production model"""
        self.set_tag("model_status", "production")
        if self._run_id:
            logger.info(f"Tagged run {self._run_id} as production model")

    def end_run(self):
        """end the active mlflow run"""
        if not self._mlflow_available:
            self._run_id = None
            return
        import mlflow
        mlflow.end_run()
        logger.info(f"Ended MLflow run: {self._run_id}")
        self._run_id = None

    def get_best_run(self, metric: str = "composite_score") -> Optional[Dict[str, Any]]:
        """get the best run from the experiment by a metric"""
        if not self._mlflow_available:
            return None
        import mlflow
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if not experiment:
            return None

        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=[f"metrics.{metric} DESC"],
            max_results=1,
        )

        if runs.empty:
            return None

        best = runs.iloc[0]
        return {
            "run_id": best["run_id"],
            metric: best.get(f"metrics.{metric}", 0),
            "params": {col.replace("params.", ""): best[col]
                       for col in runs.columns if col.startswith("params.")},
        }

    # vertex ai model registry operations

    def register_model(
        self,
        model_name: str,
        artifact_uri: Optional[str] = None,
        run_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """register a model in Vertex AI Model Registry.

        args:
            model_name: display name (e.g. "bertopic_journals")
            artifact_uri: GCS URI where model artifacts are stored
            run_id: MLflow run_id (stored as label for traceability)
            labels: additional labels to attach to the model version

        returns:
            model resource name string, or None if registry not enabled
        """
        if not self._vertex_ai_available:
            logger.warning("Vertex AI Model Registry not enabled — skipping registration")
            return None

        if not artifact_uri:
            logger.error("artifact_uri is required for Vertex AI model registration")
            return None

        from google.cloud import aiplatform

        model_labels = {
            "pipeline": "calmai",
            "model_type": model_name.replace("bertopic_", ""),
        }
        if run_id:
            # vertex ai labels must be lowercase alphanumeric + hyphens/underscores
            model_labels["mlflow_run_id"] = run_id.replace("-", "_")[:63]
        if labels:
            model_labels.update(labels)

        try:
            # use our own airflow image from artifact registry as the container.
            # vertex ai requires the URI to be from artifact registry or GCR —
            # docker hub images (e.g. python:3.10-slim) are rejected.
            # pre-built vertex ai containers (tf2, sklearn, etc.) validate the
            # artifact directory for framework-specific files (saved_model.pb,
            # model.pkl) which BERTopic doesn't produce.
            # using a custom container skips artifact validation entirely.
            # we never deploy this model to an endpoint — the registry is purely
            # a versioned catalog — so the container is never actually pulled.
            gcp_region = config.settings.GCP_REGION or "us-central1"
            gcp_project = config.settings.GCP_PROJECT_ID
            container_uri = (
                f"{gcp_region}-docker.pkg.dev/{gcp_project}"
                f"/calmai-docker/calmai-airflow:latest"
            )
            model = aiplatform.Model.upload(
                display_name=model_name,
                artifact_uri=artifact_uri,
                serving_container_image_uri=container_uri,
                serving_container_predict_route="/predict",
                serving_container_health_route="/health",
                labels=model_labels,
            )
            resource_name = model.resource_name
            logger.info(
                f"Registered model '{model_name}' in Vertex AI: {resource_name}"
            )
            return resource_name
        except Exception as e:
            logger.error(f"Vertex AI model registration failed: {e}")
            return None

    def promote_to_production(self, model_name: str, model_resource_name: str) -> bool:
        """mark a Vertex AI model version as production via labels.

        args:
            model_name: display name (for logging only)
            model_resource_name: full resource name from register_model()

        returns:
            True if successful
        """
        if not self._vertex_ai_available:
            logger.warning("Vertex AI not enabled — skipping promotion")
            return False

        from google.cloud import aiplatform

        try:
            model = aiplatform.Model(model_resource_name)
            current_labels = dict(model.labels) if model.labels else {}
            current_labels["status"] = "production"
            model.update(labels=current_labels)
            logger.info(
                f"Promoted '{model_name}' to production in Vertex AI: {model_resource_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Vertex AI promotion failed: {e}")
            return False

    def get_production_version(self, model_name: str) -> Optional[Dict[str, Any]]:
        """get the current production model from Vertex AI Model Registry.

        returns:
            dict with resource_name, display_name, artifact_uri, labels, create_time
            or None if not found
        """
        if not self._vertex_ai_available:
            return None

        from google.cloud import aiplatform

        try:
            models = aiplatform.Model.list(
                filter=f'display_name="{model_name}" AND labels.status="production"',
                order_by="create_time desc",
            )
            if not models:
                logger.info(f"No production version found for '{model_name}'")
                return None

            m = models[0]
            return {
                "resource_name": m.resource_name,
                "display_name": m.display_name,
                "artifact_uri": m.artifact_uri,
                "labels": dict(m.labels) if m.labels else {},
                "create_time": str(m.create_time),
            }
        except Exception as e:
            logger.warning(f"Could not fetch production version for '{model_name}': {e}")
            return None

    def get_archived_versions(self, model_name: str, limit: int = 5) -> list:
        """get recent model versions from Vertex AI (for rollback reference)."""
        if not self._vertex_ai_available:
            return []

        from google.cloud import aiplatform

        try:
            models = aiplatform.Model.list(
                filter=f'display_name="{model_name}"',
                order_by="create_time desc",
            )
            results = []
            for m in models[:limit]:
                results.append({
                    "resource_name": m.resource_name,
                    "artifact_uri": m.artifact_uri,
                    "labels": dict(m.labels) if m.labels else {},
                    "create_time": str(m.create_time),
                })
            return results
        except Exception as e:
            logger.warning(f"Could not fetch versions for '{model_name}': {e}")
            return []

    @property
    def run_id(self) -> Optional[str]:
        return self._run_id
