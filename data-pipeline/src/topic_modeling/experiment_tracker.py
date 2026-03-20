# mlflow experiment tracking wrapper with model registry support
# supports both file-backed (legacy) and sqlite-backed (registry) storage
# tracks hyperparameters, metrics, and model artifacts per training run
# provides model registration, stage transitions, and rollback

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import get_mlruns_dir

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """thin wrapper around mlflow for tracking topic model experiments.

    when MLFLOW_TRACKING_URI is set in config (e.g. sqlite:///path/mlflow.db),
    the tracker uses that URI and enables model registry operations.
    otherwise falls back to local file-backed storage.
    """

    def __init__(self, experiment_name: str = "journal_topic_model"):
        self.experiment_name = experiment_name
        self._run_id: Optional[str] = None
        self._registry_enabled = False
        self._mlflow_available = False
        self._setup_tracking()

    def _setup_tracking(self):
        """configure mlflow tracking URI and experiment.

        any URI scheme enables the model registry (sqlite, postgresql, http).
        the registry is used for model versioning, stage transitions, and rollback.
        if mlflow is not installed, tracking is silently disabled so training continues.
        """
        try:
            import mlflow
        except ModuleNotFoundError:
            logger.warning(
                "mlflow not installed — experiment tracking and model registry disabled. "
                "Install mlflow to enable: pip install mlflow>=3.0.0"
            )
            self._mlflow_available = False
            return

        self._mlflow_available = True

        tracking_uri = config.settings.MLFLOW_TRACKING_URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
            self._registry_enabled = True
            logger.info(
                f"MLflow tracking (registry-enabled): experiment={self.experiment_name}, "
                f"uri={tracking_uri}"
            )
        else:
            # fallback to local file-backed storage (no registry)
            mlruns_dir = get_mlruns_dir()
            tracking_uri = mlruns_dir.resolve().as_uri()
            mlflow.set_tracking_uri(tracking_uri)
            logger.warning(
                f"MLFLOW_TRACKING_URI not set — using file-backed storage (registry disabled): "
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

    @property
    def registry_enabled(self) -> bool:
        return self._registry_enabled

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
        """log a trained model directory under a named artifact subdirectory.

        uses artifact_path so the registered model URI is runs:/<run_id>/<artifact_path>.
        always call this BEFORE end_run() so the active run is still open.

        args:
            dir_path: local path to the model directory (e.g. models/bertopic_journals/latest/model)
            artifact_path: subdirectory name in the artifact store (default: "model")
        """
        if not self._mlflow_available:
            return
        import mlflow
        try:
            mlflow.log_artifacts(dir_path, artifact_path=artifact_path)
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

    # model registry operations

    def register_model(
        self,
        model_name: str,
        artifact_path: str = "model",
        run_id: Optional[str] = None,
    ) -> Optional[str]:
        """register a model version in the MLflow Model Registry.

        args:
            model_name: registered model name (e.g. "bertopic_journals")
            artifact_path: path within the run's artifacts
            run_id: run to register from (defaults to current run)

        returns:
            model version string, or None if registry not enabled
        """
        if not self._registry_enabled:
            logger.warning("Model registry not enabled — skipping registration")
            return None

        import mlflow

        rid = run_id or self._run_id
        if not rid:
            logger.error("No run_id available for model registration")
            return None

        model_uri = f"runs:/{rid}/{artifact_path}"
        try:
            result = mlflow.register_model(model_uri, model_name)
            version = result.version
            logger.info(
                f"Registered model '{model_name}' version {version} "
                f"from run {rid}"
            )
            return str(version)
        except Exception as e:
            logger.error(f"Model registration failed: {e}")
            return None

    def transition_model_stage(
        self,
        model_name: str,
        version: str,
        stage: str,
    ) -> bool:
        """transition a model version to a new stage.

        args:
            model_name: registered model name
            version: model version to transition
            stage: target stage ("Staging", "Production", "Archived")

        returns:
            True if successful
        """
        if not self._registry_enabled:
            logger.warning("Model registry not enabled — skipping stage transition")
            return False

        from mlflow import MlflowClient

        try:
            client = MlflowClient()
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
                archive_existing_versions=(stage == "Production"),
            )
            logger.info(
                f"Transitioned '{model_name}' v{version} to stage '{stage}'"
            )
            return True
        except Exception as e:
            logger.error(f"Stage transition failed: {e}")
            return False

    def promote_to_production(self, model_name: str, version: str) -> bool:
        """promote a model version to Production stage.
        automatically archives the current Production version."""
        return self.transition_model_stage(model_name, version, "Production")

    def get_production_version(self, model_name: str) -> Optional[Dict[str, Any]]:
        """get the current Production version of a registered model.

        returns:
            dict with version, run_id, source, or None
        """
        if not self._registry_enabled:
            return None

        from mlflow import MlflowClient

        try:
            client = MlflowClient()
            versions = client.get_latest_versions(model_name, stages=["Production"])
            if not versions:
                logger.info(f"No Production version found for '{model_name}'")
                return None

            v = versions[0]
            return {
                "version": v.version,
                "run_id": v.run_id,
                "source": v.source,
                "stage": v.current_stage,
                "description": v.description or "",
            }
        except Exception as e:
            logger.warning(f"Could not fetch Production version for '{model_name}': {e}")
            return None

    def get_staging_version(self, model_name: str) -> Optional[Dict[str, Any]]:
        """get the current Staging version of a registered model."""
        if not self._registry_enabled:
            return None

        from mlflow import MlflowClient

        try:
            client = MlflowClient()
            versions = client.get_latest_versions(model_name, stages=["Staging"])
            if not versions:
                return None

            v = versions[0]
            return {
                "version": v.version,
                "run_id": v.run_id,
                "source": v.source,
                "stage": v.current_stage,
            }
        except Exception as e:
            logger.warning(f"Could not fetch Staging version for '{model_name}': {e}")
            return None

    def get_archived_versions(self, model_name: str, limit: int = 5) -> list:
        """get recent Archived versions (for rollback)."""
        if not self._registry_enabled:
            return []

        from mlflow import MlflowClient

        try:
            client = MlflowClient()
            versions = client.get_latest_versions(model_name, stages=["Archived"])
            results = []
            for v in versions[:limit]:
                results.append({
                    "version": v.version,
                    "run_id": v.run_id,
                    "source": v.source,
                    "stage": v.current_stage,
                })
            return results
        except Exception as e:
            logger.warning(f"Could not fetch Archived versions for '{model_name}': {e}")
            return []

    def download_model_artifacts(self, run_id: str, artifact_path: str = "model") -> Optional[str]:
        """download model artifacts from a run.

        returns:
            local path to downloaded artifacts, or None on failure
        """
        if not self._mlflow_available:
            return None
        import mlflow

        try:
            local_path = mlflow.artifacts.download_artifacts(
                run_id=run_id, artifact_path=artifact_path
            )
            logger.info(f"Downloaded artifacts from run {run_id} to {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Artifact download failed: {e}")
            return None

    @property
    def run_id(self) -> Optional[str]:
        return self._run_id
