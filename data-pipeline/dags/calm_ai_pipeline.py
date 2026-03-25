# main airflow dag for the calmai data pipeline
# tasks: acquisition -> preprocessing -> validation -> embedding -> model training -> bias -> analytics -> mongodb -> email
# uses branchpythonoperator for validation gate and emptyoperators for sync points
# trains bertopic models for journals, conversations, and severity after embedding

from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.exceptions import AirflowFailException
import logging
import sys
import time

sys.path.insert(0, "/opt/airflow/src")
sys.path.insert(0, "/opt/airflow/configs")

from config import settings

logger = logging.getLogger("calm_ai_data_pipeline")

default_args = {
    "owner": "calmai",
    "depends_on_past": False,
    "email": ["gala.jain@northeastern.edu", "lakhani.bha@northeastern.edu", "shah.mir@northeastern.edu", "mane.prit@northeastern.edu", "adhikari.t@northeastern.edu"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# task callables
# each one wraps a pipeline step with timing and xcom

def start_callable(**context):
    settings.ensure_directories()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    context["ti"].xcom_push(key="run_id", value=run_id)
    logger.info(f"Pipeline started | run_id={run_id}")

def download_conversations_callable(**context):
    t0 = time.time()
    try:
        from acquisition.data_downloader import DataDownloader
        output_dir = settings.RAW_DATA_DIR / "conversations"
        downloader = DataDownloader(output_dir=output_dir)
        results = downloader.run(skip_existing=True)
        paths = {k: str(v) for k, v in results.items()}
        context["ti"].xcom_push(key="conversations_raw_paths", value=paths)
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Conversations downloaded: {paths}")
    except Exception as e:
        logger.error(f"download_conversations failed: {e}")
        raise

def generate_journals_callable(**context):
    t0 = time.time()
    try:
        from acquisition.generate_journals import JournalGenerator
        generator = JournalGenerator()
        output_path = generator.run(skip_existing=True)
        context["ti"].xcom_push(key="journals_raw_path", value=str(output_path))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Journals generated: {output_path}")
    except Exception as e:
        logger.error(f"generate_journals failed: {e}")
        raise

def preprocess_conversations_callable(**context):
    t0 = time.time()
    try:
        from preprocessing.conversation_preprocessor import ConversationPreprocessor
        output_path = ConversationPreprocessor().run(skip_existing=False)
        context["ti"].xcom_push(key="conversations_processed_path", value=str(output_path))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Conversations preprocessed: {output_path}")
    except Exception as e:
        logger.error(f"preprocess_conversations failed: {e}")
        raise

def preprocess_journals_callable(**context):
    t0 = time.time()
    try:
        from preprocessing.journal_preprocessor import JournalPreprocessor
        output_path = JournalPreprocessor().run(skip_existing=False)
        context["ti"].xcom_push(key="journals_processed_path", value=str(output_path))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Journals preprocessed: {output_path}")
    except Exception as e:
        logger.error(f"preprocess_journals failed: {e}")
        raise

def validate_data_callable(**context):
    t0 = time.time()
    try:
        from validation.schema_validator import SchemaValidator
        reports = SchemaValidator().run(skip_existing=False)

        all_passed = True
        total_failed = 0
        details = []

        for name, report in reports.items():
            if report is None:
                continue
            if report.failed > 0:
                all_passed = False
                total_failed += report.failed
                failed_exp = [
                    e for e in report.expectations if not e.get("success", True)
                ]
                details.append(f"{name}: {failed_exp}")

        ti = context["ti"]
        ti.xcom_push(key="validation_passed", value=all_passed)
        ti.xcom_push(key="validation_failed_count", value=total_failed)
        ti.xcom_push(key="validation_details", value=str(details))
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Validation {'PASSED' if all_passed else 'FAILED'} | failures={total_failed}"
        )
    except Exception as e:
        logger.error(f"validate_data failed: {e}")
        raise

# validation gate — routes to embed tasks on pass or halts on fail
def validation_branch_callable(**context):
    ti = context["ti"]
    passed = ti.xcom_pull(task_ids="validate_data", key="validation_passed")
    if passed:
        logger.info("Validation passed -> embedding")
        return ["embed_conversations", "embed_journals"]

    logger.warning("Validation failed -> stopping pipeline")
    return "validation_failed"

def validation_failed_callable(**context):
    details = (
        context["ti"].xcom_pull(task_ids="validate_data", key="validation_details")
        or ""
    )
    raise AirflowFailException(
        f"Pipeline halted — validation failure: {details}"
    )

def embed_conversations_callable(**context):
    t0 = time.time()
    try:
        from embedding.embedder import embed_conversations
        output_path = embed_conversations(force=True)
        context["ti"].xcom_push(
            key="conversations_embedded_path", value=str(output_path)
        )
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Conversations embedded: {output_path}")
    except Exception as e:
        logger.error(f"embed_conversations failed: {e}")
        raise

def embed_journals_callable(**context):
    t0 = time.time()
    try:
        from embedding.embedder import embed_journals
        output_path = embed_journals(force=True)
        context["ti"].xcom_push(key="journals_embedded_path", value=str(output_path))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Journals embedded: {output_path}")
    except Exception as e:
        logger.error(f"embed_journals failed: {e}")
        raise

# topic model training

def train_journal_model_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="journals")
        trainer = TopicModelTrainer(cfg)

        journals_path = context["ti"].xcom_pull(
            task_ids="embed_journals", key="journals_embedded_path"
        )

        if journals_path:
            df = pd.read_parquet(journals_path)
        else:
            df = pd.read_parquet(
                settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"
            )

        docs, timestamps = trainer.prepare_journal_docs(df)

        # use pre-calculated embeddings from the parquet if available
        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        # train to staging dir — only promoted models get copied to latest/
        staging_dir = get_staging_dir("journals")
        result = trainer.train(docs, embeddings=embeddings, timestamps=timestamps, save_dir=staging_dir)
        model_path = result.get("model_path") or str(trainer.save_model(staging_dir))

        # validate model quality
        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="journal_model_path", value=str(model_path))
        context["ti"].xcom_push(key="journal_mlflow_run_id", value=result.get("mlflow_run_id"))
        context["ti"].xcom_push(key="journal_topics", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="journal_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="journal_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Journal topic model trained: {result['num_topics']} topics, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}, "
            f"mlflow_run_id={result.get('mlflow_run_id')}"
        )
    except Exception as e:
        logger.error(f"train_journal_model failed: {e}")
        raise

def train_conversation_model_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="conversations")
        trainer = TopicModelTrainer(cfg)

        conv_path = context["ti"].xcom_pull(
            task_ids="embed_conversations", key="conversations_embedded_path"
        )

        if conv_path:
            df = pd.read_parquet(conv_path)
        else:
            df = pd.read_parquet(
                settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
            )

        docs, _ = trainer.prepare_conversation_docs(df)

        # use pre-calculated embeddings from the parquet if available
        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        # train to staging dir — only promoted models get copied to latest/
        staging_dir = get_staging_dir("conversations")
        result = trainer.train(docs, embeddings=embeddings, save_dir=staging_dir)
        model_path = result.get("model_path") or str(trainer.save_model(staging_dir))

        # validate model quality
        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="conversation_model_path", value=str(model_path))
        context["ti"].xcom_push(key="conversation_mlflow_run_id", value=result.get("mlflow_run_id"))
        context["ti"].xcom_push(key="conversation_topics", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="conversation_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="conversation_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Conversation topic model trained: {result['num_topics']} topics, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}, "
            f"mlflow_run_id={result.get('mlflow_run_id')}"
        )
    except Exception as e:
        logger.error(f"train_conversation_model failed: {e}")
        raise

def train_severity_model_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="severity")
        trainer = TopicModelTrainer(cfg)

        conv_path = context["ti"].xcom_pull(
            task_ids="embed_conversations", key="conversations_embedded_path"
        )

        if conv_path:
            df = pd.read_parquet(conv_path)
        else:
            df = pd.read_parquet(
                settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
            )

        docs, _ = trainer.prepare_conversation_docs(df)

        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        # train to staging dir — only promoted models get copied to latest/
        staging_dir = get_staging_dir("severity")
        result = trainer.train(docs, embeddings=embeddings, save_dir=staging_dir)
        model_path = result.get("model_path") or str(trainer.save_model(staging_dir))

        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="severity_model_path", value=str(model_path))
        context["ti"].xcom_push(key="severity_mlflow_run_id", value=result.get("mlflow_run_id"))
        context["ti"].xcom_push(key="severity_clusters", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="severity_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="severity_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Severity model trained: {result['num_topics']} clusters, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}, "
            f"mlflow_run_id={result.get('mlflow_run_id')}"
        )
    except Exception as e:
        logger.error(f"train_severity_model failed: {e}")
        raise

# bias analysis (runs after training so it can use the trained models)

def bias_conversations_callable(**context):
    t0 = time.time()
    try:
        from bias_detection.conversation_bias import ConversationBiasAnalyzer
        report = ConversationBiasAnalyzer().run(skip_existing=False)

        underrepresented = []
        if report and report.underrepresented_topics:
            underrepresented = report.underrepresented_topics
            if underrepresented:
                logger.warning(
                    f"Underrepresented topics (<3%): {underrepresented}"
                )

        context["ti"].xcom_push(key="underrepresented", value=underrepresented)
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Conversation bias done | underrepresented={len(underrepresented)}"
        )
    except Exception as e:
        logger.error(f"bias_conversations failed: {e}")
        raise

def bias_journals_callable(**context):
    t0 = time.time()
    try:
        from bias_detection.journal_bias import JournalBiasAnalyzer
        report = JournalBiasAnalyzer().run(skip_existing=False)

        sparse = (
            len(report.sparse_patients) if report and report.sparse_patients else 0
        )
        context["ti"].xcom_push(key="sparse_patients", value=sparse)
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Journal bias done | sparse_patients={sparse}")
    except Exception as e:
        logger.error(f"bias_journals failed: {e}")
        raise

# model lifecycle tasks (run after training + bias)

def validate_candidates_callable(**context):
    """run holdout validation on all three candidate models.
    computes clustering quality metrics (silhouette, calinski-harabasz, davies-bouldin, dbcv)
    and topic quality metrics on a held-out slice of data."""
    t0 = time.time()
    ti = context["ti"]
    try:
        import pandas as pd
        import numpy as np
        from topic_modeling.validation import TopicModelValidator
        from topic_modeling.config import TopicModelConfig

        validator = TopicModelValidator()
        reports = {}

        model_configs = [
            ("journals",      "train_journal_model",       "journal_model_path"),
            ("conversations", "train_conversation_model",  "conversation_model_path"),
            ("severity",      "train_severity_model",      "severity_model_path"),
        ]
        for model_type, train_task_id, xcom_key in model_configs:
            model_path = ti.xcom_pull(task_ids=train_task_id, key=xcom_key)
            if not model_path:
                logger.warning(f"No model path for {model_type} — skipping holdout validation")
                continue

            try:
                from bertopic import BERTopic
                import config as _cfg
                if _cfg.settings.USE_EMBEDDING_SERVICE:
                    from embedding.embedding_client import EmbeddingClient
                    from topic_modeling.trainer import _make_embedding_wrapper
                    model = BERTopic.load(model_path, embedding_model=_make_embedding_wrapper(EmbeddingClient()))
                else:
                    model = BERTopic.load(model_path)

                # load the data used for training
                if model_type == "journals":
                    data_path = ti.xcom_pull(task_ids="embed_journals", key="journals_embedded_path")
                    if data_path:
                        df = pd.read_parquet(data_path)
                    else:
                        df = pd.read_parquet(
                            settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"
                        )
                    # temporal holdout: use newest 20% as holdout
                    if "entry_date" in df.columns:
                        df = df.sort_values("entry_date")
                    split_idx = int(len(df) * 0.8)
                    holdout_df = df.iloc[split_idx:]
                    text_col = "embedding_text" if "embedding_text" in holdout_df.columns else "content"
                    holdout_docs = holdout_df[text_col].astype(str).tolist()
                else:
                    data_path = ti.xcom_pull(task_ids="embed_conversations", key="conversations_embedded_path")
                    if data_path:
                        df = pd.read_parquet(data_path)
                    else:
                        df = pd.read_parquet(
                            settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
                        )
                    # random holdout with fixed seed
                    np.random.seed(42)
                    indices = np.random.permutation(len(df))
                    split_idx = int(len(df) * 0.8)
                    holdout_df = df.iloc[indices[split_idx:]]
                    text_col = "embedding_text" if "embedding_text" in holdout_df.columns else "context"
                    holdout_docs = holdout_df[text_col].astype(str).tolist()

                holdout_embeddings = None
                if "embedding" in holdout_df.columns:
                    holdout_embeddings = np.array(holdout_df["embedding"].tolist())

                report = validator.validate_holdout(model, holdout_docs, holdout_embeddings)
                report["model_type"] = model_type
                reports[model_type] = report
                validator.save_report(report, f"{model_type}_holdout_validation.json")
                logger.info(
                    f"Holdout validation for {model_type}: status={report['status']}, "
                    f"silhouette={report['metrics'].get('silhouette_score', 'N/A')}"
                )
            except Exception as e:
                logger.error(f"Holdout validation failed for {model_type}: {e}")
                reports[model_type] = {"status": "error", "error": str(e)}

        # convert numpy arrays to lists so XCom can JSON-serialize the reports
        def _json_safe(obj):
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _json_safe(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_json_safe(v) for v in obj]
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            return obj

        ti.xcom_push(key="holdout_reports", value=_json_safe(reports))
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Candidate validation complete: {len(reports)} models evaluated")
    except Exception as e:
        logger.error(f"validate_candidates failed: {e}")
        raise


def bias_gate_candidates_callable(**context):
    """run holdout bias gate on candidate models.
    checks for per-slice disparities between candidate and active predictions."""
    t0 = time.time()
    ti = context["ti"]
    try:
        import pandas as pd
        import numpy as np
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        bias_results = {}

        holdout_reports = ti.xcom_pull(task_ids="validate_candidates", key="holdout_reports") or {}

        for model_type, report in holdout_reports.items():
            if report.get("status") == "error":
                continue

            try:
                holdout_topics = report.get("holdout_topics", [])
                num_topics = report.get("metrics", {}).get("num_topics", 0)

                # load holdout df for slicing
                if model_type == "journals":
                    data_path = ti.xcom_pull(task_ids="embed_journals", key="journals_embedded_path")
                    if data_path:
                        df = pd.read_parquet(data_path)
                    else:
                        df = pd.read_parquet(
                            settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"
                        )
                    if "entry_date" in df.columns:
                        df = df.sort_values("entry_date")
                    split_idx = int(len(df) * 0.8)
                    holdout_df = df.iloc[split_idx:]
                else:
                    data_path = ti.xcom_pull(task_ids="embed_conversations", key="conversations_embedded_path")
                    if data_path:
                        df = pd.read_parquet(data_path)
                    else:
                        df = pd.read_parquet(
                            settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
                        )
                    np.random.seed(42)
                    indices = np.random.permutation(len(df))
                    split_idx = int(len(df) * 0.8)
                    holdout_df = df.iloc[indices[split_idx:]]

                holdout_df = holdout_df.reset_index(drop=True)

                result = gate.evaluate(
                    holdout_df=holdout_df,
                    candidate_topics=holdout_topics,
                    candidate_probs=None,
                    num_topics=num_topics,
                )
                bias_results[model_type] = result
                logger.info(
                    f"Bias gate for {model_type}: passed={result['passed']}, "
                    f"max_disparity={result['max_disparity_delta']}"
                )
            except Exception as e:
                logger.error(f"Bias gate failed for {model_type}: {e}")
                bias_results[model_type] = {"passed": False, "error": str(e)}

        ti.xcom_push(key="bias_gate_results", value=bias_results)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
    except Exception as e:
        logger.error(f"bias_gate_candidates failed: {e}")
        raise


def selection_decision_callable(**context):
    """run selection policy: hard gates + weighted scoring for each model type."""
    t0 = time.time()
    ti = context["ti"]
    try:
        from topic_modeling.selection_policy import SelectionPolicy
        from topic_modeling.validation import TopicModelValidator

        # relaxed gates for demo pipeline — first-run setup with limited data
        policy = SelectionPolicy(overrides={"min_silhouette": 0.01})
        holdout_reports = ti.xcom_pull(task_ids="validate_candidates", key="holdout_reports") or {}
        bias_results = ti.xcom_pull(task_ids="bias_gate_candidates", key="bias_gate_results") or {}

        decisions = {}
        any_promoted = False

        for model_type, candidate_report in holdout_reports.items():
            if candidate_report.get("status") == "error":
                decisions[model_type] = {"decision": "reject", "reasons": ["validation_error"]}
                continue

            bias_result = bias_results.get(model_type)
            decision = policy.evaluate(
                candidate_report=candidate_report,
                active_report=None,  # first run — no active model to compare
                bias_result=bias_result,
            )
            decisions[model_type] = decision
            if decision["decision"] == "promote":
                any_promoted = True

            logger.info(f"Selection for {model_type}: {decision['decision']} — {decision['reasons']}")

        ti.xcom_push(key="selection_decisions", value=decisions)
        ti.xcom_push(key="any_promoted", value=any_promoted)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Selection complete: any_promoted={any_promoted}")
    except Exception as e:
        logger.error(f"selection_decision failed: {e}")
        raise


def selection_branch_callable(**context):
    """branch based on selection decisions."""
    ti = context["ti"]
    any_promoted = ti.xcom_pull(task_ids="selection_decision", key="any_promoted")
    if any_promoted:
        logger.info("Selection gate PASSED — proceeding to promotion")
        return "register_and_promote_models"
    logger.info("Selection gate FAILED — keeping current models")
    return "selection_rejected"


def _upload_model_to_gcs(model_path: str, gcs_key: str):
    """upload a local model directory to GCS with versioning.

    returns the full gs:// URI of the versioned upload on success, or None on failure.
    """
    bucket_name = settings.MODEL_REGISTRY_BUCKET
    if not bucket_name:
        logger.warning("MODEL_REGISTRY_BUCKET not set — skipping GCS upload")
        return None
    try:
        from pathlib import Path
        from datetime import datetime, timezone
        from google.cloud import storage as gcs
        key_file = settings.GCS_KEY_FILE
        client = gcs.Client.from_service_account_json(key_file) if Path(key_file).exists() else gcs.Client()
        bucket = client.bucket(bucket_name)
        model_dir = Path(model_path)
        if not model_dir.exists():
            logger.warning(f"Model path does not exist, skipping GCS upload: {model_path}")
            return None
        version_tag = datetime.now(timezone.utc).strftime("v_%Y%m%d_%H%M%S")
        files = list(model_dir.rglob("*")) if model_dir.is_dir() else [model_dir]
        uploaded = 0
        for f in files:
            if f.is_file():
                rel = f.relative_to(model_dir)
                # versioned copy only (no latest/ on GCS — local latest/ is the source of truth)
                bucket.blob(f"{gcs_key}/{version_tag}/{rel}").upload_from_filename(str(f))
                uploaded += 1
        gcs_uri = f"gs://{bucket_name}/{gcs_key}/{version_tag}"
        logger.info(f"GCS upload: {uploaded} files → {gcs_uri}/")
        return gcs_uri
    except Exception as e:
        logger.warning(f"GCS upload failed for {model_path}: {e}")
        return None


def selection_rejected_callable(**context):
    """log rejection, upload rejected models to GCS for audit, clean up staging.
    local latest/ is NOT touched — the previously promoted model stays active."""
    ti = context["ti"]
    decisions = ti.xcom_pull(task_ids="selection_decision", key="selection_decisions") or {}
    reasons = {k: v.get("reasons", []) for k, v in decisions.items() if v.get("decision") == "reject"}
    logger.warning(f"Model promotion rejected: {reasons}")

    from topic_modeling.config import cleanup_staging

    try:
        from storage.mongodb_client import MongoDBClient
        client = MongoDBClient()
        try:
            client.connect()
            _task_key_map = {
                "journals":      ("train_journal_model",      "journal_"),
                "conversations": ("train_conversation_model", "conversation_"),
                "severity":      ("train_severity_model",     "severity_"),
            }
            for model_type, decision in decisions.items():
                if decision.get("decision") != "reject":
                    continue

                train_task, key_prefix = _task_key_map.get(model_type, (f"train_{model_type}_model", f"{model_type}_"))
                model_path = ti.xcom_pull(task_ids=train_task, key=f"{key_prefix}model_path")
                mlflow_run_id = ti.xcom_pull(task_ids=train_task, key=f"{key_prefix}mlflow_run_id")

                # upload rejected model to GCS for audit/comparison
                if model_path:
                    run_label = mlflow_run_id or "unknown_run"
                    gcs_key = f"{settings.MODEL_REGISTRY_PREFIX}/{model_type}/rejected/{run_label}"
                    _upload_model_to_gcs(model_path, gcs_key)

                # clean up staging — rejected model should not linger locally
                cleanup_staging(model_type)

                client.save_model_lifecycle_event({
                    "event_type": "rejection",
                    "model_name": f"bertopic_{model_type}",
                    "model_path": str(model_path) if model_path else None,
                    "mlflow_run_id": mlflow_run_id,
                    "reasons": decision.get("reasons", []),
                    "candidate_score": decision.get("candidate_score", 0),
                })
        finally:
            client.close()
    except Exception as e:
        logger.warning(f"Failed to log rejection event: {e}")


def register_and_promote_models_callable(**context):
    """register promoted models with Vertex AI Model Registry and log lifecycle events.

    uploads model artifacts to GCS first, then registers the GCS URI with Vertex AI.
    mlflow is used only for experiment tracking — registry is handled by Vertex AI.
    """
    t0 = time.time()
    ti = context["ti"]
    try:
        from topic_modeling.experiment_tracker import ExperimentTracker
        from topic_modeling.rollback import smoke_test_model
        from topic_modeling.config import promote_staging_to_latest, cleanup_staging
        from storage.mongodb_client import MongoDBClient

        decisions = ti.xcom_pull(task_ids="selection_decision", key="selection_decisions") or {}
        promotion_results = {}

        _task_key_map = {
            "journals":      ("train_journal_model",      "journal_"),
            "conversations": ("train_conversation_model", "conversation_"),
            "severity":      ("train_severity_model",     "severity_"),
        }
        for model_type, decision in decisions.items():
            if decision.get("decision") != "promote":
                continue

            train_task, key_prefix = _task_key_map.get(model_type, (f"train_{model_type}_model", f"{model_type}_"))
            model_path = ti.xcom_pull(task_ids=train_task, key=f"{key_prefix}model_path")
            mlflow_run_id = ti.xcom_pull(task_ids=train_task, key=f"{key_prefix}mlflow_run_id")

            if not model_path:
                logger.warning(f"No model path for {model_type} — skipping promotion")
                continue

            model_name = f"bertopic_{model_type}"
            logger.info(
                f"Promoting {model_name}: model_path={model_path}, "
                f"mlflow_run_id={mlflow_run_id}"
            )

            # smoke test before promotion
            sample_docs = [
                "I feel anxious about work",
                "Had a productive therapy session today",
                "Struggling with sleep and depression",
            ]
            smoke = smoke_test_model(model_name, model_path, sample_docs)
            if not smoke.get("passed", False):
                logger.error(f"Smoke test failed for {model_type}: {smoke}")
                promotion_results[model_type] = {"promoted": False, "reason": "smoke_test_failed", "smoke": smoke}
                continue

            logger.info(f"Smoke test passed for {model_type}: {smoke}")

            # promote: copy staging → latest (this is the model that inference will use)
            latest_path = promote_staging_to_latest(model_type)
            logger.info(f"Promoted {model_type} staging → latest at {latest_path}")

            # post-deployment verification on the promoted model
            try:
                from monitoring.deployment_verifier import verify_deployed_model
                verification = verify_deployed_model(
                    model_type=model_type,
                    model_dir=str(latest_path / "model") if (latest_path / "model").exists() else str(latest_path),
                )
                if not verification.get("passed", False):
                    logger.warning(f"Deployment verification FAILED for {model_type}: {verification['checks']}")
                else:
                    logger.info(f"Deployment verification passed for {model_type}")
            except Exception as e:
                logger.warning(f"Deployment verification error for {model_type} (non-blocking): {e}")

            # upload promoted model to GCS first (Vertex AI needs the GCS URI)
            run_label = mlflow_run_id or "unknown_run"
            gcs_key = f"{settings.MODEL_REGISTRY_PREFIX}/{model_type}/promoted/{run_label}"
            gcs_uri = _upload_model_to_gcs(model_path, gcs_key)

            # register with Vertex AI Model Registry (requires GCS artifact URI)
            tracker = ExperimentTracker(experiment_name=f"{model_type}_topic_model")
            resource_name = None
            if tracker.registry_enabled:
                if gcs_uri:
                    resource_name = tracker.register_model(
                        model_name,
                        artifact_uri=gcs_uri,
                        run_id=mlflow_run_id,
                    )
                    if resource_name:
                        ok = tracker.promote_to_production(model_name, resource_name)
                        if ok:
                            logger.info(f"Promoted {model_name} in Vertex AI: {resource_name}")
                        else:
                            logger.error(f"Vertex AI promotion failed for {model_name}")
                    else:
                        logger.error(f"Vertex AI registration failed for {model_name}")
                else:
                    logger.warning(
                        f"GCS upload failed — skipping Vertex AI registration for {model_name}"
                    )
            else:
                logger.info(f"Vertex AI not enabled — {model_name} saved locally at {model_path}")

            # log lifecycle event to MongoDB
            try:
                client = MongoDBClient()
                client.connect()
                try:
                    client.save_model_lifecycle_event({
                        "event_type": "promotion",
                        "model_name": model_name,
                        "resource_name": resource_name,
                        "model_path": str(model_path),
                        "mlflow_run_id": mlflow_run_id,
                        "candidate_score": decision.get("candidate_score", 0),
                        "smoke_test": smoke,
                    })
                finally:
                    client.close()
            except Exception as e:
                logger.warning(f"Failed to log promotion event for {model_type}: {e}")

            # clean up staging — model is now in latest/ and GCS
            cleanup_staging(model_type)

            promotion_results[model_type] = {
                "promoted": True,
                "resource_name": resource_name,
                "model_path": str(model_path),
                "mlflow_run_id": mlflow_run_id,
                "gcs_uri": gcs_uri,
            }

        ti.xcom_push(key="promotion_results", value=promotion_results)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Promotion complete: {promotion_results}")
    except Exception as e:
        logger.error(f"register_and_promote_models failed: {e}")
        raise


# patient analytics (runs after bias, uses trained model)

def compute_patient_analytics_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from analytics.patient_analytics import PatientAnalytics
        from storage.mongodb_client import MongoDBClient

        pa = PatientAnalytics()
        df = pd.read_parquet(
            settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
        )

        patient_ids = df["patient_id"].unique().tolist()

        # upsert to mongodb
        client = MongoDBClient()
        try:
            client.connect()
            for patient_id in patient_ids:
                patient_df = df[df["patient_id"] == patient_id]
                journals = patient_df.to_dict(orient="records")
                analytics = pa.compute_patient_analytics(journals)
                client.upsert_patient_analytics(str(patient_id), analytics)
            logger.info(f"Upserted analytics for {len(patient_ids)} patients")
        finally:
            client.close()

        context["ti"].xcom_push(key="patients_analyzed", value=len(patient_ids))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Patient analytics complete for {len(patient_ids)} patients")
    except Exception as e:
        logger.error(f"compute_patient_analytics failed: {e}")
        raise

def store_to_mongodb_callable(**context):
    t0 = time.time()
    try:
        from storage.mongodb_client import MongoDBClient
        ti = context["ti"]
        client = MongoDBClient()
        try:
            client.connect()
            client.create_indexes()
            conv_result = client.store_conversations_from_parquet()
            jour_result = client.store_journals_from_parquet()

            # classify conversations with bertopic topics + bertopic severity
            try:
                classify_result = client.classify_and_update_conversations()
                logger.info(f"Conversation classification: {classify_result}")
                ti.xcom_push(key="classify_result", value=classify_result)
            except Exception as ce:
                logger.warning(f"Conversation classification failed (non-fatal): {ce}")

            # classify journals with bertopic topics (sets themes field)
            try:
                journal_classify = client.classify_and_update_journals()
                logger.info(f"Journal classification: {journal_classify}")
                ti.xcom_push(key="journal_classify_result", value=journal_classify)
            except Exception as je:
                logger.warning(f"Journal classification failed (non-fatal): {je}")

            stats = client.get_collection_stats()

            run_id = ti.xcom_pull(task_ids="start", key="run_id") or "unknown"

            task_ids = [
                "download_conversations",
                "generate_journals",
                "preprocess_conversations",
                "preprocess_journals",
                "validate_data",
                "embed_conversations",
                "embed_journals",
                "train_journal_model",
                "train_conversation_model",
                "train_severity_model",
                "bias_conversations",
                "bias_journals",
                "compute_patient_analytics",
            ]
            metrics = {}
            for tid in task_ids:
                val = ti.xcom_pull(task_ids=tid, key="duration")
                if val is not None:
                    metrics[tid] = val
            metrics["store_to_mongodb"] = round(time.time() - t0, 2)

            client.log_pipeline_run(
                {
                    "run_id": run_id,
                    "run_date": datetime.now(timezone.utc).isoformat(),
                    "metrics": metrics,
                    "insert_results": {
                        "conversations": conv_result,
                        "journals": jour_result,
                    },
                    "collection_stats": stats,
                }
            )

            ti.xcom_push(
                key="insert_results",
                value={"conversations": conv_result, "journals": jour_result},
            )
            ti.xcom_push(key="collection_stats", value=stats)
            ti.xcom_push(key="duration", value=metrics["store_to_mongodb"])
            logger.info(f"MongoDB storage complete | {stats}")
        finally:
            client.close()
    except Exception as e:
        logger.error(f"store_to_mongodb failed: {e}")
        raise

def success_email_callable(**context):
    from alerts.success_email import send_success_email
    send_success_email(**context)

# define and configure the dag
with DAG(
    dag_id="calm_ai_data_pipeline",
    default_args=default_args,
    description=(
        "CalmAI data pipeline: acquisition, preprocessing, validation, "
        "embedding, topic model training, bias analysis, patient analytics and MongoDB storage"
    ),
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["calmai", "mental-health", "data-pipeline"],
) as dag:

    # task definitions

    t_start = PythonOperator(
        task_id="start",
        python_callable=start_callable,
    )

    t_download_conv = PythonOperator(
        task_id="download_conversations",
        python_callable=download_conversations_callable,
    )
    t_generate_jour = PythonOperator(
        task_id="generate_journals",
        python_callable=generate_journals_callable,
    )

    t_preprocess_conv = PythonOperator(
        task_id="preprocess_conversations",
        python_callable=preprocess_conversations_callable,
    )
    t_preprocess_jour = PythonOperator(
        task_id="preprocess_journals",
        python_callable=preprocess_journals_callable,
    )

    # sync points
    t_preprocessing_complete = EmptyOperator(task_id="preprocessing_complete")

    t_validate = PythonOperator(
        task_id="validate_data",
        python_callable=validate_data_callable,
    )

    t_val_branch = BranchPythonOperator(
        task_id="validation_branch",
        python_callable=validation_branch_callable,
    )

    t_val_failed = PythonOperator(
        task_id="validation_failed",
        python_callable=validation_failed_callable,
    )

    t_embed_conv = PythonOperator(
        task_id="embed_conversations",
        python_callable=embed_conversations_callable,
    )
    t_embed_jour = PythonOperator(
        task_id="embed_journals",
        python_callable=embed_journals_callable,
    )

    t_embedding_complete = EmptyOperator(task_id="embedding_complete")

    t_train_jour = PythonOperator(
        task_id="train_journal_model",
        python_callable=train_journal_model_callable,
    )
    t_train_conv = PythonOperator(
        task_id="train_conversation_model",
        python_callable=train_conversation_model_callable,
    )
    t_train_severity = PythonOperator(
        task_id="train_severity_model",
        python_callable=train_severity_model_callable,
    )

    t_training_complete = EmptyOperator(task_id="training_complete")

    t_bias_conv = PythonOperator(
        task_id="bias_conversations",
        python_callable=bias_conversations_callable,
    )
    t_bias_jour = PythonOperator(
        task_id="bias_journals",
        python_callable=bias_journals_callable,
    )

    t_bias_complete = EmptyOperator(task_id="bias_complete")

    # model lifecycle tasks
    t_validate_candidates = PythonOperator(
        task_id="validate_candidates",
        python_callable=validate_candidates_callable,
    )

    t_bias_gate = PythonOperator(
        task_id="bias_gate_candidates",
        python_callable=bias_gate_candidates_callable,
    )

    t_selection = PythonOperator(
        task_id="selection_decision",
        python_callable=selection_decision_callable,
    )

    t_selection_branch = BranchPythonOperator(
        task_id="selection_branch",
        python_callable=selection_branch_callable,
    )

    t_selection_rejected = PythonOperator(
        task_id="selection_rejected",
        python_callable=selection_rejected_callable,
    )

    t_register_promote = PythonOperator(
        task_id="register_and_promote_models",
        python_callable=register_and_promote_models_callable,
    )

    t_lifecycle_complete = EmptyOperator(
        task_id="lifecycle_complete",
        trigger_rule="none_failed_min_one_success",
    )

    t_compute_analytics = PythonOperator(
        task_id="compute_patient_analytics",
        python_callable=compute_patient_analytics_callable,
    )

    t_store = PythonOperator(
        task_id="store_to_mongodb",
        python_callable=store_to_mongodb_callable,
    )

    t_success_email = PythonOperator(
        task_id="success_email",
        python_callable=success_email_callable,
    )

    t_end = EmptyOperator(
        task_id="end",
        trigger_rule="none_failed_min_one_success",
    )

    # dependency graph
    #
    # start → [download_conv, generate_jour] → [preprocess_conv, preprocess_jour] →
    # preprocessing_complete → validate → branch
    #   ├─ (pass) → [embed_conv, embed_jour] → embedding_complete →
    #   │  [train_jour_model, train_conv_model, train_severity_model] → training_complete →
    #   │  [bias_conv, bias_jour] → bias_complete →
    #   │  validate_candidates → bias_gate_candidates → selection_decision → selection_branch
    #   │    ├─ (promote) → register_and_promote_models → lifecycle_complete
    #   │    └─ (reject) → selection_rejected → lifecycle_complete
    #   │  lifecycle_complete → compute_analytics → store_to_mongodb → success_email → end
    #   └─ (fail) → validation_failed → end

    t_start >> [t_download_conv, t_generate_jour]

    t_download_conv >> t_preprocess_conv
    t_generate_jour >> t_preprocess_jour

    [t_preprocess_conv, t_preprocess_jour] >> t_preprocessing_complete

    t_preprocessing_complete >> t_validate >> t_val_branch

    t_val_branch >> [t_embed_conv, t_embed_jour]
    t_val_branch >> t_val_failed

    [t_embed_conv, t_embed_jour] >> t_embedding_complete

    t_embedding_complete >> [t_train_jour, t_train_conv, t_train_severity]

    [t_train_jour, t_train_conv, t_train_severity] >> t_training_complete

    t_training_complete >> [t_bias_conv, t_bias_jour]

    [t_bias_conv, t_bias_jour] >> t_bias_complete

    # model lifecycle chain
    t_bias_complete >> t_validate_candidates >> t_bias_gate >> t_selection >> t_selection_branch

    t_selection_branch >> t_register_promote
    t_selection_branch >> t_selection_rejected

    [t_register_promote, t_selection_rejected] >> t_lifecycle_complete

    t_lifecycle_complete >> t_compute_analytics >> t_store >> t_success_email

    [t_success_email, t_val_failed] >> t_end
