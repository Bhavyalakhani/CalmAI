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
    import config
    config.settings.ensure_directories()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    context["ti"].xcom_push(key="run_id", value=run_id)
    logger.info(f"Pipeline started | run_id={run_id}")

def download_conversations_callable(**context):
    t0 = time.time()
    try:
        import config
        from acquisition.data_downloader import DataDownloader
        output_dir = config.settings.RAW_DATA_DIR / "conversations"
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
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="journals")
        trainer = TopicModelTrainer(cfg)

        journals_path = context["ti"].xcom_pull(
            task_ids="embed_journals", key="journals_embedded_path"
        )

        if journals_path:
            df = pd.read_parquet(journals_path)
        else:
            import config
            df = pd.read_parquet(
                config.settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"
            )

        docs, timestamps = trainer.prepare_journal_docs(df)

        # use pre-calculated embeddings from the parquet if available
        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        result = trainer.train(docs, embeddings=embeddings, timestamps=timestamps)
        model_path = trainer.save_model()

        # validate model quality
        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="journal_model_path", value=str(model_path))
        context["ti"].xcom_push(key="journal_topics", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="journal_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="journal_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Journal topic model trained: {result['num_topics']} topics, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}"
        )
    except Exception as e:
        logger.error(f"train_journal_model failed: {e}")
        raise

def train_conversation_model_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="conversations")
        trainer = TopicModelTrainer(cfg)

        conv_path = context["ti"].xcom_pull(
            task_ids="embed_conversations", key="conversations_embedded_path"
        )

        if conv_path:
            df = pd.read_parquet(conv_path)
        else:
            import config
            df = pd.read_parquet(
                config.settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
            )

        docs, _ = trainer.prepare_conversation_docs(df)

        # use pre-calculated embeddings from the parquet if available
        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        result = trainer.train(docs, embeddings=embeddings)
        model_path = trainer.save_model()

        # validate model quality
        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="conversation_model_path", value=str(model_path))
        context["ti"].xcom_push(key="conversation_topics", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="conversation_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="conversation_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Conversation topic model trained: {result['num_topics']} topics, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}"
        )
    except Exception as e:
        logger.error(f"train_conversation_model failed: {e}")
        raise

def train_severity_model_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="severity")
        trainer = TopicModelTrainer(cfg)

        conv_path = context["ti"].xcom_pull(
            task_ids="embed_conversations", key="conversations_embedded_path"
        )

        if conv_path:
            df = pd.read_parquet(conv_path)
        else:
            import config
            df = pd.read_parquet(
                config.settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"
            )

        docs, _ = trainer.prepare_conversation_docs(df)

        import numpy as np
        embeddings = None
        if "embedding" in df.columns:
            embeddings = np.array(df["embedding"].tolist())

        result = trainer.train(docs, embeddings=embeddings)
        model_path = trainer.save_model()

        validator = TopicModelValidator()
        validation_report = validator.validate(result)
        validator.save_report(validation_report)

        context["ti"].xcom_push(key="severity_model_path", value=str(model_path))
        context["ti"].xcom_push(key="severity_clusters", value=result.get("num_topics", 0))
        context["ti"].xcom_push(key="severity_outlier_ratio", value=result.get("outlier_ratio", 0))
        context["ti"].xcom_push(key="severity_model_status", value=validation_report.get("status", "unknown"))
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(
            f"Severity model trained: {result['num_topics']} clusters, "
            f"outlier_ratio={result['outlier_ratio']}, status={validation_report['status']}"
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

# patient analytics (runs after bias, uses trained model)

def compute_patient_analytics_callable(**context):
    t0 = time.time()
    try:
        import pandas as pd
        from analytics.patient_analytics import PatientAnalytics
        from storage.mongodb_client import MongoDBClient
        import config

        pa = PatientAnalytics()
        df = pd.read_parquet(
            config.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
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
    #   │  [bias_conv, bias_jour] → bias_complete → compute_analytics →
    #   │  store_to_mongodb → success_email → end
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

    t_bias_complete >> t_compute_analytics >> t_store >> t_success_email

    [t_success_email, t_val_failed] >> t_end
