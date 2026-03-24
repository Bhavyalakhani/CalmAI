# post-deployment verification for promoted BERTopic models
# runs after model promotion to verify the model is serving correctly
# checks: model loadable, inference works, topic count reasonable, latency acceptable
#
# used by DAG 1 and DAG 2 after promote_staging_to_latest

import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# sample documents for verification inference
VERIFICATION_DOCS = [
    "I have been feeling very anxious and stressed about work lately.",
    "My therapist suggested breathing exercises and they helped.",
    "I had a really positive day today and felt happy.",
    "Sleep has been difficult and I keep having nightmares.",
    "Family relationships have been improving after our last session.",
]


def verify_deployed_model(
    model_type: str,
    model_dir: str,
    test_docs: Optional[List[str]] = None,
    max_latency_ms: float = 5000.0,
) -> Dict[str, Any]:
    """verify a promoted model is serving correctly.

    checks:
    1. model can be loaded from disk
    2. inference produces valid results
    3. topic assignments are integers (not all -1 outliers)
    4. inference latency is within acceptable bounds

    args:
        model_type: e.g. "journals", "conversations", "severity"
        model_dir: path to the model directory (latest/)
        test_docs: custom test documents (defaults to built-in samples)
        max_latency_ms: max acceptable inference latency in milliseconds

    returns:
        verification report dict with passed/failed status and details
    """
    if test_docs is None:
        test_docs = VERIFICATION_DOCS

    report = {
        "model_type": model_type,
        "model_dir": model_dir,
        "checks": {},
        "passed": False,
    }

    # check 1: model loads
    try:
        from bertopic import BERTopic
        t0 = time.time()
        model = BERTopic.load(model_dir)
        load_time_ms = (time.time() - t0) * 1000
        report["checks"]["load"] = {
            "passed": True,
            "load_time_ms": round(load_time_ms, 1),
        }
    except Exception as e:
        report["checks"]["load"] = {"passed": False, "error": f"load_failed: {e}"}
        logger.error(f"Deployment verification FAILED for {model_type}: model load error — {e}")
        return report

    # check 2: inference produces results (pre-embed via EmbeddingClient)
    try:
        from embedding.embedding_client import EmbeddingClient
        client = EmbeddingClient()
        test_embeddings = client.embed(test_docs, show_progress=False)

        t0 = time.time()
        topics, probs = model.transform(test_docs, test_embeddings)
        latency_ms = (time.time() - t0) * 1000
        topics = list(topics)

        report["checks"]["inference"] = {
            "passed": True,
            "num_docs": len(test_docs),
            "num_topics_assigned": len(set(topics)),
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as e:
        report["checks"]["inference"] = {"passed": False, "error": f"inference_failed: {e}"}
        logger.error(f"Deployment verification FAILED for {model_type}: inference error — {e}")
        return report

    # check 3: topic assignments are valid
    all_outlier = all(t == -1 for t in topics)
    valid_types = all(isinstance(t, (int, np.integer)) for t in topics) if topics else True

    report["checks"]["topic_quality"] = {
        "passed": not all_outlier and valid_types,
        "all_outlier": all_outlier,
        "valid_types": valid_types,
        "topic_assignments": topics,
    }

    # check 4: latency is within bounds
    report["checks"]["latency"] = {
        "passed": latency_ms <= max_latency_ms,
        "latency_ms": round(latency_ms, 1),
        "max_latency_ms": max_latency_ms,
    }

    # overall result — all checks must pass
    all_passed = all(check["passed"] for check in report["checks"].values())
    report["passed"] = all_passed

    if all_passed:
        logger.info(
            f"Deployment verification PASSED for {model_type}: "
            f"load={report['checks']['load']['load_time_ms']:.0f}ms, "
            f"inference={latency_ms:.0f}ms, "
            f"topics={len(set(topics))}"
        )
    else:
        failed = [k for k, v in report["checks"].items() if not v["passed"]]
        logger.warning(f"Deployment verification FAILED for {model_type}: failed checks = {failed}")

    return report
