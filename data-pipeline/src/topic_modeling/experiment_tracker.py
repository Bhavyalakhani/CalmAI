# mlflow experiment tracking wrapper
# file-backed storage in data-pipeline/mlruns/
# tracks hyperparameters, metrics, and model artifacts per training run

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))

from .config import get_mlruns_dir

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """thin wrapper around mlflow for tracking topic model experiments"""

    def __init__(self, experiment_name: str = "journal_topic_model"):
        self.experiment_name = experiment_name
        self._run_id: Optional[str] = None
        self._setup_tracking()

    def _setup_tracking(self):
        """configure mlflow to use local file storage"""
        import mlflow
        mlruns_dir = get_mlruns_dir()
        tracking_uri = mlruns_dir.resolve().as_uri()
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(self.experiment_name)
        logger.info(f"MLflow tracking: experiment={self.experiment_name}, uri={tracking_uri}")

    def start_run(self, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        """start a new mlflow run and optionally log parameters"""
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
        import mlflow
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        logger.info(f"Logged metrics: {metrics}")

    def log_params(self, params: Dict[str, Any]):
        """log additional parameters to the active run"""
        import mlflow
        for key, value in params.items():
            mlflow.log_param(key, str(value))

    def log_artifact(self, path: str):
        """log a file artifact to the active run"""
        import mlflow
        mlflow.log_artifact(path)
        logger.info(f"Logged artifact: {path}")

    def log_artifacts_dir(self, dir_path: str):
        """log all files in a directory as artifacts"""
        import mlflow
        mlflow.log_artifacts(dir_path)
        logger.info(f"Logged artifacts directory: {dir_path}")

    def set_tag(self, key: str, value: str):
        """set a tag on the active run"""
        import mlflow
        mlflow.set_tag(key, value)

    def tag_best_model(self):
        """tag the current run as the best/production model"""
        self.set_tag("model_status", "production")
        logger.info(f"Tagged run {self._run_id} as production model")

    def end_run(self):
        """end the active mlflow run"""
        import mlflow
        mlflow.end_run()
        logger.info(f"Ended MLflow run: {self._run_id}")
        self._run_id = None

    def get_best_run(self, metric: str = "composite_score") -> Optional[Dict[str, Any]]:
        """get the best run from the experiment by a metric"""
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

    @property
    def run_id(self) -> Optional[str]:
        return self._run_id
