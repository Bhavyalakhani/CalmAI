# model rollback utilities
# handles automatic and manual rollback of promoted models
# transitions the most recent Archived version back to Production

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))

from .experiment_tracker import ExperimentTracker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ModelRollback:
    """handles rolling back a model from Production to a previous version.

    rollback flow:
    1. find the current Production version
    2. find the most recent Archived version (previous known-good)
    3. archive the current Production
    4. promote the Archived version back to Production
    5. log the rollback event
    """

    def __init__(self, tracker: Optional[ExperimentTracker] = None):
        self.tracker = tracker

    def rollback(
        self,
        model_name: str,
        reason: str = "manual_rollback",
        tracker: Optional[ExperimentTracker] = None,
    ) -> Dict[str, Any]:
        """execute a rollback for the given model.

        args:
            model_name: registered model name (e.g. "bertopic_journals")
            reason: description of why rollback was triggered
            tracker: ExperimentTracker to use (overrides self.tracker)

        returns:
            rollback result dict with success/failure details
        """
        trk = tracker or self.tracker
        if trk is None or not trk.registry_enabled:
            logger.error("Rollback requires a registry-enabled ExperimentTracker")
            return {
                "success": False,
                "reason": reason,
                "error": "registry_not_enabled",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"Starting rollback for '{model_name}': reason={reason}")

        # get current production version
        prod = trk.get_production_version(model_name)
        if prod is None:
            logger.warning(f"No Production version found for '{model_name}' — nothing to rollback")
            return {
                "success": False,
                "reason": reason,
                "error": "no_production_version",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # get most recent archived version
        archived = trk.get_archived_versions(model_name, limit=1)
        if not archived:
            logger.error(f"No Archived version available for '{model_name}' — cannot rollback")
            return {
                "success": False,
                "reason": reason,
                "error": "no_archived_version",
                "rolled_back_from": prod["version"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        rollback_target = archived[0]

        # archive the current production
        logger.info(
            f"Archiving current Production v{prod['version']}, "
            f"restoring Archived v{rollback_target['version']}"
        )

        archived_ok = trk.transition_model_stage(
            model_name, prod["version"], "Archived"
        )
        if not archived_ok:
            return {
                "success": False,
                "reason": reason,
                "error": "failed_to_archive_current",
                "rolled_back_from": prod["version"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # promote the archived version back to production
        promoted_ok = trk.transition_model_stage(
            model_name, rollback_target["version"], "Production"
        )
        if not promoted_ok:
            # try to restore original production
            logger.error("Failed to promote rollback target — attempting to restore original")
            trk.transition_model_stage(model_name, prod["version"], "Production")
            return {
                "success": False,
                "reason": reason,
                "error": "failed_to_promote_rollback_target",
                "rolled_back_from": prod["version"],
                "rollback_target": rollback_target["version"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        result = {
            "success": True,
            "reason": reason,
            "rolled_back_from": prod["version"],
            "rolled_back_to": rollback_target["version"],
            "model_name": model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Rollback successful for '{model_name}': "
            f"v{prod['version']} -> v{rollback_target['version']} | reason={reason}"
        )
        return result


def smoke_test_model(model_name: str, model_path: str, sample_docs: list) -> Dict[str, Any]:
    """run a basic smoke test on a promoted model.

    loads the model, runs sample inference, and validates output shape.

    args:
        model_name: name for logging
        model_path: local path to model directory
        sample_docs: list of sample documents to test inference

    returns:
        dict with passed (bool) and details
    """
    logger.info(f"Running smoke test for '{model_name}' at {model_path}")

    try:
        from bertopic import BERTopic
        model = BERTopic.load(model_path)
    except Exception as e:
        logger.error(f"Smoke test FAILED — model load error: {e}")
        return {"passed": False, "error": f"load_failed: {e}"}

    if not sample_docs:
        logger.warning("No sample docs provided — skipping inference test")
        return {"passed": True, "warning": "no_sample_docs"}

    try:
        topics, probs = model.transform(sample_docs)

        if len(topics) != len(sample_docs):
            return {
                "passed": False,
                "error": f"topic count mismatch: {len(topics)} vs {len(sample_docs)} docs",
            }

        # check topics are integers
        for t in topics:
            if not isinstance(t, (int, np.integer)):
                return {"passed": False, "error": f"non-integer topic: {t} ({type(t)})"}

        logger.info(
            f"Smoke test PASSED: {len(sample_docs)} docs -> "
            f"{len(set(topics))} unique topics"
        )
        return {
            "passed": True,
            "num_docs": len(sample_docs),
            "unique_topics": len(set(topics)),
            "outlier_count": sum(1 for t in topics if t == -1),
        }

    except Exception as e:
        logger.error(f"Smoke test FAILED — inference error: {e}")
        return {"passed": False, "error": f"inference_failed: {e}"}
