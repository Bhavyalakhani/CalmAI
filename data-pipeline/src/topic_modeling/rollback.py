# smoke test utility for validating model artifacts before promotion
# loads the model, runs sample inference, and validates output shape

import logging
from typing import Dict, Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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
