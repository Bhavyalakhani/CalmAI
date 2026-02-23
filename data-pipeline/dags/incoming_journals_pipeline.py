# dag 2 — incoming journal micro-batch pipeline
# fetches unprocessed journals from mongodb, preprocesses, validates, embeds,
# stores, updates analytics (using trained bertopic model) and sends email notifications
# schedule: every 30 minutes | short-circuits if no new entries

from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.operators.empty import EmptyOperator
import logging
import sys
import time

sys.path.insert(0, "/opt/airflow/src")
sys.path.insert(0, "/opt/airflow/configs")

logger = logging.getLogger("incoming_journals_pipeline")

default_args = {
    "owner": "calmai",
    "depends_on_past": False,
    "email": ["gala.jain@northeastern.edu", "lakhani.bha@northeastern.edu", "shah.mir@northeastern.edu", "mane.prit@northeastern.edu", "adhikari.t@northeastern.edu"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


# task callables

def fetch_new_entries_callable(**context):
    """fetch unprocessed journals from incoming_journals collection.
    short-circuits (returns false) if no new entries."""
    import time
    from storage.mongodb_client import MongoDBClient
    t0 = time.time()
    ti = context["ti"]
    client = MongoDBClient()
    try:
        client.connect()
        docs = client.fetch_unprocessed_journals()

        if not docs:
            logger.info("No unprocessed journals found — short-circuiting")
            ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
            return False

        # convert objectid to string for xcom serialization
        serializable = []
        for doc in docs:
            doc["_id"] = str(doc.get("_id", ""))
            serializable.append(doc)

        ti.xcom_push(key="incoming_journals", value=serializable)
        ti.xcom_push(key="journal_count", value=len(serializable))
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Fetched {len(serializable)} unprocessed journals")
        return True
    finally:
        client.close()


def preprocess_entries_callable(**context):
    """preprocess incoming journal dicts using JournalPreprocessor methods.
    operates in-memory (no file i/o) and pushes `preprocessed_journals` to xcom."""
    t0 = time.time()
    ti = context["ti"]
    journals = ti.xcom_pull(task_ids="fetch_new_entries", key="incoming_journals")

    if not journals:
        logger.warning("No journals to preprocess")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    from preprocessing.journal_preprocessor import process_incoming_journals

    try:
        records = process_incoming_journals(journals)
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        raise

    ti.xcom_push(key="preprocessed_journals", value=records)
    ti.xcom_push(key="preprocessed_count", value=len(records))
    ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
    logger.info(f"Preprocessed {len(records)} incoming journals")


def validate_entries_callable(**context):
    """validate incoming journals using schema validator.
    filters out invalid entries and passes valid ones downstream."""
    t0 = time.time()
    ti = context["ti"]
    # prefer preprocessed journals (new preprocess step); fall back to fetched ones
    journals = ti.xcom_pull(task_ids="preprocess_entries", key="preprocessed_journals")
    if journals is None:
        journals = ti.xcom_pull(task_ids="fetch_new_entries", key="incoming_journals")

    if not journals:
        logger.warning("No journals to validate")
        context["ti"].xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    import pandas as pd
    from validation.schema_validator import SchemaValidator

    df = pd.DataFrame(journals)
    validator = SchemaValidator()
    results = validator.validate_incoming_journals(df)

    # check for any failures
    failed = [r for r in results if not r.success]
    if failed:
        logger.warning(f"Validation issues ({len(failed)}): {[r.name for r in failed]}")
        # filter out rows with empty or null content but continue processing
        if "content" in df.columns:
            original_count = len(df)
            df = df[df["content"].astype(str).str.strip().str.len() > 0]
            if len(df) < original_count:
                logger.info(f"Filtered {original_count - len(df)} empty entries")

    # pass validated journals forward
    valid_journals = df.to_dict("records")
    ti.xcom_push(key="valid_journals", value=valid_journals)
    ti.xcom_push(key="valid_count", value=len(valid_journals))
    ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
    logger.info(f"Validation complete: {len(valid_journals)} valid journals")


def embed_entries_callable(**context):
    """embed validated incoming journals"""
    t0 = time.time()
    ti = context["ti"]
    journals = ti.xcom_pull(task_ids="validate_entries", key="valid_journals")

    if not journals:
        logger.warning("No valid journals to embed")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    from embedding.embedder import embed_incoming_journals
    embedded_df = embed_incoming_journals(journals)

    # create JSON-safe records for XCom: convert pd.Timestamp -> ISO string
    records = []
    for r in embedded_df.to_dict("records"):
        if "entry_date" in r and r["entry_date"] is not None:
            try:
                # r["entry_date"] may already be a string if sanitized elsewhere
                if not isinstance(r["entry_date"], str):
                    r["entry_date"] = pd.Timestamp(r["entry_date"]).isoformat()
            except Exception:
                # fallback: leave as-is
                pass
        records.append(r)
    ti.xcom_push(key="embedded_journals", value=records)
    ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
    logger.info(f"Embedded {len(records)} incoming journals")


def store_to_mongodb_callable(**context):
    """store embedded journals to rag_vectors + journals (append mode)"""
    t0 = time.time()
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="embed_entries", key="embedded_journals")

    if not records:
        logger.warning("No embedded journals to store")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    import pandas as pd
    from storage.mongodb_client import MongoDBClient

    df = pd.DataFrame(records)
    client = MongoDBClient()
    try:
        client.connect()
        result = client.insert_incoming_journals(df)
        ti.xcom_push(key="insert_result", value=result)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Stored incoming journals: {result}")
    finally:
        client.close()


def update_analytics_callable(**context):
    """recompute patient analytics for affected patients"""
    t0 = time.time()
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="embed_entries", key="embedded_journals")

    if not records:
        logger.warning("No journals — skipping analytics update")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    import pandas as pd
    from storage.mongodb_client import MongoDBClient
    from analytics.patient_analytics import PatientAnalytics

    df = pd.DataFrame(records)
    patient_ids = df["patient_id"].dropna().unique().tolist()

    analytics_service = PatientAnalytics()
    client = MongoDBClient()
    try:
        client.connect()

        for pid in patient_ids:
            # fetch all journals for this patient from the journals collection
            all_journals = list(client.journals.find({"patient_id": pid}))
            if all_journals:
                analytics = analytics_service.compute_patient_analytics(all_journals)
                client.upsert_patient_analytics(pid, analytics)
                logger.info(f"Updated analytics for patient {pid}: {analytics['total_entries']} entries")

        ti.xcom_push(key="patients_updated", value=len(patient_ids))
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Analytics updated for {len(patient_ids)} patients")
    finally:
        client.close()


def mark_processed_callable(**context):
    """mark the fetched journals as processed in incoming_journals collection"""
    t0 = time.time()
    ti = context["ti"]
    journals = ti.xcom_pull(task_ids="fetch_new_entries", key="incoming_journals")

    if not journals:
        logger.warning("No journals to mark as processed")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        return

    from storage.mongodb_client import MongoDBClient

    journal_ids = [j["journal_id"] for j in journals if "journal_id" in j]
    client = MongoDBClient()
    try:
        client.connect()
        client.mark_journals_processed(journal_ids)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Marked {len(journal_ids)} journals as processed")
    finally:
        client.close()


# dag definition

with DAG(
    dag_id="incoming_journals_pipeline",
    default_args=default_args,
    description=(
        "Micro-batch pipeline for incoming patient journals: "
        "fetch, preprocess, validate, embed, store, update analytics"
    ),
    schedule="*/30 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["calmai", "mental-health", "incoming-journals", "micro-batch"],
    max_active_runs=1,
) as dag:

    def start_callable(**context):
        """Initialize run metadata for incoming micro-batch and push run_id + duration.

        Uses the same run id format as the main `calm_ai_pipeline` (YYYYMMDD_HHMMSS).
        """
        import time
        from datetime import datetime, timezone

        ti = context["ti"]

        # Follow calm_ai_pipeline: generate a timestamp-based run_id
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        ti.xcom_push(key="run_id", value=run_id)
        ti.xcom_push(key="duration", value=0)
        logger.info(f"Start task initialized run_id={run_id}")

    t_start = PythonOperator(task_id="start", python_callable=start_callable)

    # short-circuits the entire dag if no new entries
    t_fetch = ShortCircuitOperator(
        task_id="fetch_new_entries",
        python_callable=fetch_new_entries_callable,
    )

    t_preprocess = PythonOperator(
        task_id="preprocess_entries",
        python_callable=preprocess_entries_callable,
    )

    t_validate = PythonOperator(
        task_id="validate_entries",
        python_callable=validate_entries_callable,
    )

    t_embed = PythonOperator(
        task_id="embed_entries",
        python_callable=embed_entries_callable,
    )

    t_store = PythonOperator(
        task_id="store_to_mongodb",
        python_callable=store_to_mongodb_callable,
    )

    t_analytics = PythonOperator(
        task_id="update_analytics",
        python_callable=update_analytics_callable,
    )

    t_mark = PythonOperator(
        task_id="mark_processed",
        python_callable=mark_processed_callable,
    )

    def success_email_callable(**context):
        from alerts.success_email import send_incoming_success_email
        send_incoming_success_email(**context)

    t_success_email = PythonOperator(
        task_id="success_email",
        python_callable=success_email_callable,
    )

    t_end = EmptyOperator(
        task_id="end",
        trigger_rule="none_failed_min_one_success",
    )

    # dependency graph
    t_start >> t_fetch >> t_preprocess >> t_validate >> t_embed >> t_store >> t_analytics >> t_mark >> t_success_email >> t_end
