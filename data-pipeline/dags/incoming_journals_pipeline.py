# dag 2 — incoming journal micro-batch pipeline
# fetches unprocessed journals from mongodb, preprocesses, validates, embeds,
# stores, conditionally retrains bertopic models, updates analytics and sends email notifications
# schedule: every 12 hours | short-circuits if no new entries

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

    import pandas as pd
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


def conditional_retrain_callable(**context):
    """conditionally retrain all three bertopic models when thresholds are met.
    triggers when either:
    - 50+ new journal entries since last training, or
    - 7+ days since last training
    reads full corpus from mongodb (not parquet) so models learn from all data."""
    t0 = time.time()
    ti = context["ti"]

    from storage.mongodb_client import MongoDBClient
    from config import settings

    threshold_entries = settings.RETRAIN_ENTRY_THRESHOLD
    threshold_days = settings.RETRAIN_MAX_DAYS

    client = MongoDBClient()
    try:
        client.connect()

        # check current corpus sizes
        current_journal_count = client.journals.count_documents({})
        current_conversation_count = client.conversations.count_documents({})

        # get last training metadata
        last_training = client.get_last_training_metadata()

        should_retrain = False
        retrain_reason = ""

        if last_training is None:
            # no training metadata found — first run after implementing this feature
            # skip retrain since models were trained by dag 1
            logger.info("No training metadata found — saving baseline counts (models from DAG 1)")
            client.save_training_metadata({
                "journal_count": current_journal_count,
                "conversation_count": current_conversation_count,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "reason": "baseline",
            })
            ti.xcom_push(key="retrain_triggered", value=False)
            ti.xcom_push(key="retrain_reason", value="baseline metadata saved")
            ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
            return

        # check entry threshold
        last_journal_count = last_training.get("journal_count", 0)
        new_entries = current_journal_count - last_journal_count
        if new_entries >= threshold_entries:
            should_retrain = True
            retrain_reason = f"{new_entries} new entries since last training (threshold: {threshold_entries})"

        # check time threshold
        if not should_retrain:
            last_trained_at = last_training.get("trained_at")
            if last_trained_at:
                from datetime import datetime as dt
                if isinstance(last_trained_at, str):
                    last_dt = dt.fromisoformat(last_trained_at.replace("Z", "+00:00"))
                else:
                    last_dt = last_trained_at
                days_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
                if days_since >= threshold_days:
                    should_retrain = True
                    retrain_reason = f"{days_since:.1f} days since last training (threshold: {threshold_days})"

        # data drift detection — check when volume/time thresholds are NOT met
        if not should_retrain and settings.ENABLE_DRIFT_DETECTION:
            try:
                from monitoring.drift_detector import DriftDetector
                import pandas as pd

                detector = DriftDetector(
                    vocab_threshold=settings.DRIFT_VOCAB_THRESHOLD,
                    embedding_threshold=settings.DRIFT_EMBEDDING_THRESHOLD,
                    topic_threshold=settings.DRIFT_TOPIC_THRESHOLD,
                )

                # fetch recent incoming docs and a sample of training corpus for comparison
                recent_docs = list(client.db["incoming_journals"].find(
                    {"is_processed": True},
                    {"content": 1, "_id": 0},
                ).sort("created_at", -1).limit(200))
                recent_texts = [d["content"] for d in recent_docs if d.get("content")]

                training_docs = list(client.journals.find(
                    {},
                    {"content": 1, "_id": 0},
                ).sort("entry_date", -1).limit(500))
                training_texts = [d["content"] for d in training_docs if d.get("content")]

                if len(recent_texts) >= 10 and len(training_texts) >= 10:
                    drift_report = detector.run_drift_check(
                        reference_docs=training_texts,
                        current_docs=recent_texts,
                    )
                    logger.info(f"Drift check: {drift_report}")
                    ti.xcom_push(key="drift_report", value=drift_report)

                    if drift_report.get("drift_detected", False):
                        should_retrain = True
                        drift_signals = []
                        for signal in ["vocabulary", "embedding", "topic"]:
                            if drift_report.get(signal, {}).get("drifted", False):
                                drift_signals.append(signal)
                        retrain_reason = f"data drift detected: {', '.join(drift_signals)}"
                else:
                    logger.info(f"Drift check skipped — too few docs (recent={len(recent_texts)}, training={len(training_texts)})")
            except Exception as e:
                logger.warning(f"Drift detection failed (non-blocking): {e}")

        if not should_retrain:
            logger.info(f"Retrain not needed — {new_entries} new entries, thresholds not met, no drift")
            ti.xcom_push(key="retrain_triggered", value=False)
            ti.xcom_push(key="retrain_reason", value="thresholds not met")
            ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
            return

        logger.info(f"Retrain triggered: {retrain_reason}")

        # fetch full corpus from mongodb
        import pandas as pd
        all_journals = list(client.journals.find({}))
        all_conversations = list(client.conversations.find({}))

        journal_df = pd.DataFrame(all_journals) if all_journals else pd.DataFrame()
        conversation_df = pd.DataFrame(all_conversations) if all_conversations else pd.DataFrame()

        logger.info(f"Loaded {len(journal_df)} journals and {len(conversation_df)} conversations from MongoDB")

        from topic_modeling.config import TopicModelConfig, get_models_dir, get_staging_dir, promote_staging_to_latest, cleanup_staging
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.validation import TopicModelValidator
        from topic_modeling.selection_policy import SelectionPolicy
        from topic_modeling.rollback import smoke_test_model

        retrain_results = {}
        validator = TopicModelValidator()
        policy = SelectionPolicy()

        def _retrain_single_model(model_type, df, prepare_fn, **train_kwargs):
            """retrain a single model with full lifecycle:
            train → holdout validate → compare with existing latest/ model →
            bias gate → selection policy → smoke test → promote or reject.
            trains to staging/ dir — only promoted models get copied to latest/."""
            import numpy as np
            from pathlib import Path

            cfg = TopicModelConfig(model_type=model_type)
            trainer = TopicModelTrainer(cfg)
            docs_and_extra = prepare_fn(df)
            docs = docs_and_extra[0]
            timestamps = docs_and_extra[1] if len(docs_and_extra) > 1 else None

            kwargs = {"embeddings": None}
            if timestamps:
                kwargs["timestamps"] = timestamps
            kwargs.update(train_kwargs)

            # 1. train to staging dir (not latest/)
            staging_dir = get_staging_dir(model_type)
            result = trainer.train(docs, save_dir=staging_dir, **kwargs)
            model_path = result.get("model_path") or str(trainer.save_model(staging_dir))

            # 2. basic validation
            validation_report = validator.validate(result)
            validator.save_report(validation_report)

            # 3. holdout validation + bias gate + active model comparison
            holdout_report = None
            active_report = None
            bias_result = None
            try:
                from bertopic import BERTopic
                model = BERTopic.load(str(model_path))

                # split data 80/20 (temporal for journals, random for others)
                if model_type == "journals" and "entry_date" in df.columns:
                    sorted_df = df.sort_values("entry_date")
                    split_idx = int(len(sorted_df) * 0.8)
                    holdout_df = sorted_df.iloc[split_idx:].reset_index(drop=True)
                    holdout_docs = docs[split_idx:]
                else:
                    rng = np.random.default_rng(42)
                    indices = rng.permutation(len(df))
                    split_idx = int(len(df) * 0.8)
                    holdout_indices = indices[split_idx:]
                    holdout_df = df.iloc[holdout_indices].reset_index(drop=True)
                    holdout_docs = [docs[i] for i in holdout_indices]

                # holdout validation on candidate
                holdout_report = validator.validate_holdout(model, holdout_docs)
                holdout_report["model_type"] = model_type
                validator.save_report(holdout_report, f"{model_type}_retrain_holdout.json")

                # holdout validation on existing latest/ model (for comparison)
                latest_dir = get_models_dir(model_type)
                latest_model_path = latest_dir / "model"
                if latest_model_path.exists():
                    try:
                        active_model = BERTopic.load(str(latest_model_path))
                        active_report = validator.validate_holdout(active_model, holdout_docs)
                        active_report["model_type"] = f"{model_type}_active"
                        validator.save_report(active_report, f"{model_type}_active_holdout.json")
                        logger.info(
                            f"{model_type}: active model holdout composite_score="
                            f"{active_report.get('metrics', {}).get('composite_score', 'N/A')}"
                        )
                    except Exception as e:
                        logger.warning(f"{model_type}: could not validate active model (non-fatal): {e}")
                else:
                    logger.info(f"{model_type}: no existing latest/ model — first promotion")

                # bias gate
                from bias_detection.holdout_bias_gate import HoldoutBiasGate
                gate = HoldoutBiasGate()
                holdout_topics, holdout_probs = model.transform(holdout_docs)
                bias_result = gate.evaluate(
                    holdout_df=holdout_df,
                    candidate_topics=list(holdout_topics),
                    candidate_probs=holdout_probs,
                    num_topics=result.get("num_topics", 0),
                )
                logger.info(
                    f"{model_type}: holdout={holdout_report.get('status')}, "
                    f"bias_passed={bias_result.get('passed')}, "
                    f"disparity={bias_result.get('max_disparity_delta')}"
                )
            except Exception as e:
                logger.warning(f"{model_type}: holdout/bias analysis failed (non-fatal): {e}")

            # 4. selection policy — compare candidate vs existing latest/ model
            candidate = holdout_report if holdout_report else validation_report
            decision = policy.evaluate(
                candidate_report=candidate,
                active_report=active_report,
                bias_result=bias_result,
            )

            # 5. smoke test if promoted
            promoted = False
            if decision.get("decision") == "promote":
                smoke = smoke_test_model(
                    f"bertopic_{model_type}", str(model_path),
                    docs[:3] if len(docs) >= 3 else docs,
                )
                if smoke.get("passed", False):
                    promoted = True
                    # copy staging → latest (this is the model inference will use)
                    promote_staging_to_latest(model_type)
                    logger.info(f"{model_type}: promoted after retrain — staging → latest")

                    # 6. post-deployment verification on the promoted model
                    try:
                        from monitoring.deployment_verifier import verify_deployed_model
                        latest_dir = get_models_dir(model_type) / "model"
                        verification = verify_deployed_model(
                            model_type=model_type,
                            model_dir=str(latest_dir),
                        )
                        if not verification.get("passed", False):
                            logger.warning(f"{model_type}: deployment verification FAILED — {verification['checks']}")
                        else:
                            logger.info(f"{model_type}: deployment verification passed")
                    except Exception as e:
                        logger.warning(f"{model_type}: deployment verification error (non-blocking): {e}")
                else:
                    logger.warning(f"{model_type}: smoke test failed — {smoke}")

            # build result before cleanup (model_path still exists on disk)
            retrain_result = {
                "num_topics": result["num_topics"],
                "num_documents": result["num_documents"],
                "outlier_ratio": result["outlier_ratio"],
                "validation_status": validation_report.get("status", "unknown"),
                "holdout_status": holdout_report.get("status", "unknown") if holdout_report else "skipped",
                "active_composite_score": active_report.get("metrics", {}).get("composite_score", 0) if active_report else None,
                "bias_passed": bias_result.get("passed") if bias_result else None,
                "bias_max_disparity": bias_result.get("max_disparity_delta") if bias_result else None,
                "composite_score": (holdout_report or validation_report).get("metrics", {}).get("composite_score", 0),
                "decision": decision.get("decision", "unknown"),
                "promoted": promoted,
                "model_path": str(model_path),
            }

            # 6. cleanup staging AFTER result is built (GCS upload uses model_path later)
            # for promoted models, staging was already copied to latest/
            # for rejected models, we keep staging alive until GCS upload completes
            if promoted:
                cleanup_staging(model_type)

            return retrain_result

        # retrain journal model
        if len(journal_df) >= 20:
            try:
                retrain_results["journals"] = _retrain_single_model(
                    "journals", journal_df,
                    lambda df: TopicModelTrainer.prepare_journal_docs(df),
                )
                logger.info(f"Journal model retrained: {retrain_results['journals']}")
            except Exception as e:
                logger.error(f"Journal model retrain failed: {e}")
                retrain_results["journals"] = {"error": str(e)}
        else:
            logger.info(f"Skipping journal model — only {len(journal_df)} docs (need 20+)")

        # retrain conversation model
        if len(conversation_df) >= 20:
            try:
                retrain_results["conversations"] = _retrain_single_model(
                    "conversations", conversation_df,
                    lambda df: TopicModelTrainer.prepare_conversation_docs(df),
                )
                logger.info(f"Conversation model retrained: {retrain_results['conversations']}")
            except Exception as e:
                logger.error(f"Conversation model retrain failed: {e}")
                retrain_results["conversations"] = {"error": str(e)}
        else:
            logger.info(f"Skipping conversation model — only {len(conversation_df)} docs (need 20+)")

        # retrain severity model (uses conversation data)
        if len(conversation_df) >= 20:
            try:
                retrain_results["severity"] = _retrain_single_model(
                    "severity", conversation_df,
                    lambda df: TopicModelTrainer.prepare_conversation_docs(df),
                )
                logger.info(f"Severity model retrained: {retrain_results['severity']}")
            except Exception as e:
                logger.error(f"Severity model retrain failed: {e}")
                retrain_results["severity"] = {"error": str(e)}
        else:
            logger.info(f"Skipping severity model — only {len(conversation_df)} docs (need 20+)")

        # save new training metadata
        client.save_training_metadata({
            "journal_count": current_journal_count,
            "conversation_count": current_conversation_count,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "reason": retrain_reason,
            "results": retrain_results,
        })

        # upload all models to GCS (promoted + rejected) then clean up rejected staging
        from pathlib import Path
        import config as _cfg
        _settings = _cfg.settings
        bucket_name = _settings.MODEL_REGISTRY_BUCKET
        key_file = Path(_settings.GCS_KEY_FILE)

        if bucket_name and key_file.exists():
            try:
                from google.cloud import storage as gcs
                gcs_client = gcs.Client.from_service_account_json(str(key_file))
                bucket = gcs_client.bucket(bucket_name)
                prefix = _settings.MODEL_REGISTRY_PREFIX
                version_tag = datetime.now(timezone.utc).strftime("v_%Y%m%d_%H%M%S")

                gcs_uris = {}  # model_type → GCS URI for Vertex AI registration
                for model_type, res in retrain_results.items():
                    if "error" in res:
                        continue
                    model_dir = Path(res["model_path"])
                    if not model_dir.exists():
                        continue

                    status = "promoted" if res.get("promoted", False) else "rejected"
                    gcs_prefix = f"{prefix}/bertopic_{model_type}/{status}/{version_tag}"
                    files = [f for f in model_dir.rglob("*") if f.is_file()] if model_dir.is_dir() else [model_dir]
                    for f in files:
                        rel = f.relative_to(model_dir) if model_dir.is_dir() else f.name
                        bucket.blob(f"{gcs_prefix}/{rel}").upload_from_filename(str(f))
                    logger.info(f"GCS upload: bertopic_{model_type} → {status}/{version_tag}/")

                    if res.get("promoted", False):
                        gcs_uris[model_type] = f"gs://{bucket_name}/{gcs_prefix}"

                # register promoted models with Vertex AI Model Registry
                if gcs_uris:
                    try:
                        from topic_modeling.experiment_tracker import ExperimentTracker
                        for model_type, gcs_uri in gcs_uris.items():
                            tracker = ExperimentTracker(experiment_name=f"{model_type}_topic_model")
                            if not tracker.registry_enabled:
                                logger.info(f"Vertex AI not enabled — skipping registration for bertopic_{model_type}")
                                continue
                            model_name = f"bertopic_{model_type}"
                            resource_name = tracker.register_model(
                                model_name,
                                artifact_uri=gcs_uri,
                                labels={"retrain_trigger": retrain_reason[:63]},
                            )
                            if resource_name:
                                tracker.promote_to_production(model_name, resource_name)
                                logger.info(f"Registered + promoted {model_name} in Vertex AI: {resource_name}")
                            else:
                                logger.warning(f"Vertex AI registration failed for {model_name}")
                    except Exception as e:
                        logger.warning(f"Vertex AI registration after retrain failed (non-blocking): {e}")

            except Exception as e:
                logger.warning(f"GCS upload after retrain failed (non-blocking): {e}")
        elif not bucket_name:
            logger.info("MODEL_REGISTRY_BUCKET not set — skipping GCS upload")
        elif not key_file.exists():
            logger.info(f"GCS key file not found: {key_file} — skipping GCS upload")

        # clean up rejected staging dirs now that GCS upload is done
        for model_type, res in retrain_results.items():
            if "error" in res:
                continue
            if not res.get("promoted", False):
                cleanup_staging(model_type)

        ti.xcom_push(key="retrain_triggered", value=True)
        ti.xcom_push(key="retrain_reason", value=retrain_reason)
        ti.xcom_push(key="retrain_results", value=retrain_results)
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        logger.info(f"Conditional retrain complete: {retrain_reason}")

    except Exception as e:
        logger.error(f"Conditional retrain failed: {e}")
        ti.xcom_push(key="retrain_triggered", value=False)
        ti.xcom_push(key="retrain_reason", value=f"error: {e}")
        ti.xcom_push(key="duration", value=round(time.time() - t0, 2))
        raise
    finally:
        client.close()


def update_analytics_callable(**context):
    """recompute patient analytics for affected patients.
    if a retrain just happened, the new model is already on disk and will be loaded."""
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
        "fetch, preprocess, validate, embed, store, conditional retrain, update analytics"
    ),
    schedule="0 */12 * * *",
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

    t_retrain = PythonOperator(
        task_id="conditional_retrain",
        python_callable=conditional_retrain_callable,
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
    t_start >> t_fetch >> t_preprocess >> t_validate >> t_embed >> t_store >> t_retrain >> t_analytics >> t_mark >> t_success_email >> t_end
