# local pipeline runner (no airflow)
# mirrors the full dag: acquire -> preprocess -> validate -> bias -> embed -> store
# with timing for each step and a validation gate that halts on failure

import sys
import time
import logging
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent / "src"))

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("pipeline")

# helpers

DIVIDER = "=" * 60
TOTAL_STEPS = 17


def step(number, name):
    logger.info(f"\n{DIVIDER}\n  Step {number}/{TOTAL_STEPS} — {name}\n{DIVIDER}")


def timed(fn):
    start = time.time()
    result = fn()
    elapsed = time.time() - start
    logger.info(f"  completed in {elapsed:.1f}s")
    return result, elapsed


def run():
    settings = config.settings
    settings.ensure_directories()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    metrics = {}
    logger.info(f"Pipeline run: {run_id}")

    # 1. download huggingface conversation datasets
    step(1, "Download conversations")
    from acquisition.data_downloader import DataDownloader

    def download_conversations():
        output_dir = settings.RAW_DATA_DIR / "conversations"
        downloader = DataDownloader(output_dir=output_dir)
        return downloader.run(skip_existing=True)

    download_results, metrics["download_conversations"] = timed(download_conversations)
    for name, path in download_results.items():
        logger.info(f"  {name} → {path}")

    # 2. generate synthetic journals via gemini api
    step(2, "Generate journals")
    from acquisition.generate_journals import JournalGenerator

    def generate_journals():
        generator = JournalGenerator()
        return generator.run(skip_existing=True)

    journal_path, metrics["generate_journals"] = timed(generate_journals)
    logger.info(f"  journals → {journal_path}")

    # 3. preprocess conversations
    step(3, "Preprocess conversations")
    from preprocessing.conversation_preprocessor import ConversationPreprocessor

    def preprocess_conversations():
        return ConversationPreprocessor().run(skip_existing=False)

    _, metrics["preprocess_conversations"] = timed(preprocess_conversations)

    # 4. preprocess journals
    step(4, "Preprocess journals")
    from preprocessing.journal_preprocessor import JournalPreprocessor

    def preprocess_journals():
        return JournalPreprocessor().run(skip_existing=False)

    _, metrics["preprocess_journals"] = timed(preprocess_journals)

    # 5. schema validation (halts pipeline on failure)
    step(5, "Validate data")
    from validation.schema_validator import SchemaValidator

    def validate_data():
        return SchemaValidator().run(skip_existing=False)

    reports, metrics["validate_data"] = timed(validate_data)

    all_passed = True
    total_failed = 0
    for name, report in reports.items():
        if report is None:
            continue
        if report.failed > 0:
            all_passed = False
            total_failed += report.failed
            failed_expectations = [
                e for e in report.expectations if not e.get("success", True)
            ]
            logger.error(f"  {name} failed: {failed_expectations}")

    if not all_passed:
        logger.error(f"Validation FAILED with {total_failed} failures — halting pipeline")
        sys.exit(1)

    logger.info("validation passed — continuing to embedding")

    # 6. embed both datasets
    step(6, "Embed conversations + journals")
    from embedding.embedder import embed_conversations, embed_journals

    def run_embed_conversations():
        return embed_conversations(force=True)

    conv_emb_path, metrics["embed_conversations"] = timed(run_embed_conversations)
    logger.info(f"  conversations → {conv_emb_path}")

    def run_embed_journals():
        return embed_journals(force=True)

    jour_emb_path, metrics["embed_journals"] = timed(run_embed_journals)
    logger.info(f"  journals      → {jour_emb_path}")

    # 7. train journal topic model (requires bertopic / umap / hdbscan)
    step(7, "Train journal topic model")

    def train_journal_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="journals")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(jour_emb_path)
        docs, timestamps = trainer.prepare_journal_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        staging_dir = get_staging_dir("journals")
        result = trainer.train(docs, embeddings=embeddings, timestamps=timestamps, save_dir=staging_dir)
        model_path = trainer.save_model(staging_dir)
        validator = TopicModelValidator()
        report = validator.validate(result)
        validator.save_report(report)
        return {
            "model_path": str(model_path),
            "num_topics": result.get("num_topics", 0),
            "outlier_ratio": result.get("outlier_ratio", 0),
            "status": report.get("status", "unknown"),
        }

    try:
        journal_model_info, metrics["train_journal_model"] = timed(train_journal_model)
        logger.info(f"  journal model: {journal_model_info['num_topics']} topics, status={journal_model_info['status']}")
    except Exception as e:
        logger.warning(f"  journal model training skipped: {e}")
        metrics["train_journal_model"] = 0

    # 8. train conversation topic model (requires bertopic / umap / hdbscan)
    step(8, "Train conversation topic model")

    def train_conversation_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="conversations")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(conv_emb_path)
        docs, _ = trainer.prepare_conversation_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        staging_dir = get_staging_dir("conversations")
        result = trainer.train(docs, embeddings=embeddings, save_dir=staging_dir)
        model_path = trainer.save_model(staging_dir)
        validator = TopicModelValidator()
        report = validator.validate(result)
        validator.save_report(report)
        return {
            "model_path": str(model_path),
            "num_topics": result.get("num_topics", 0),
            "outlier_ratio": result.get("outlier_ratio", 0),
            "status": report.get("status", "unknown"),
        }

    try:
        conv_model_info, metrics["train_conversation_model"] = timed(train_conversation_model)
        logger.info(f"  conversation model: {conv_model_info['num_topics']} topics, status={conv_model_info['status']}")
    except Exception as e:
        logger.warning(f"  conversation model training skipped: {e}")
        metrics["train_conversation_model"] = 0

    # 9. train severity model (uses same conversation embeddings with severity prompt)
    step(9, "Train severity model")

    def train_severity_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig, get_staging_dir
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="severity")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(conv_emb_path)
        docs, _ = trainer.prepare_conversation_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        staging_dir = get_staging_dir("severity")
        result = trainer.train(docs, embeddings=embeddings, save_dir=staging_dir)
        model_path = trainer.save_model(staging_dir)
        validator = TopicModelValidator()
        report = validator.validate(result)
        validator.save_report(report)
        return {
            "model_path": str(model_path),
            "num_clusters": result.get("num_topics", 0),
            "outlier_ratio": result.get("outlier_ratio", 0),
            "status": report.get("status", "unknown"),
        }

    try:
        severity_model_info, metrics["train_severity_model"] = timed(train_severity_model)
        logger.info(f"  severity model: {severity_model_info['num_clusters']} clusters, status={severity_model_info['status']}")
    except Exception as e:
        logger.warning(f"  severity model training skipped: {e}")
        metrics["train_severity_model"] = 0

    # 10. bias analysis — conversations (requires trained conversation model)
    step(10, "Bias analysis — conversations")
    from bias_detection.conversation_bias import ConversationBiasAnalyzer

    def bias_conversations():
        report = ConversationBiasAnalyzer().run(skip_existing=False)
        if report and report.underrepresented_topics:
            logger.warning(f"  underrepresented topics (<3%): {report.underrepresented_topics}")
        return report

    _, metrics["bias_conversations"] = timed(bias_conversations)

    # 11. bias analysis — journals (requires trained journal model)
    step(11, "Bias analysis — journals")
    from bias_detection.journal_bias import JournalBiasAnalyzer

    def bias_journals():
        report = JournalBiasAnalyzer().run(skip_existing=False)
        if report and report.sparse_patients:
            logger.warning(f"  sparse patients (<10 entries): {len(report.sparse_patients)}")
        return report

    _, metrics["bias_journals"] = timed(bias_journals)

    # 12. validate candidate models (holdout)
    step(12, "Validate candidate models")

    holdout_reports = {}

    def validate_candidates():
        import numpy as np
        from topic_modeling.validation import TopicModelValidator
        from bertopic import BERTopic

        validator = TopicModelValidator()
        reports = {}

        model_configs = {
            "journals": (jour_emb_path, "embedding_text", "entry_date", True),
            "conversations": (conv_emb_path, "embedding_text", None, False),
            "severity": (conv_emb_path, "embedding_text", None, False),
        }

        for model_type, (data_path, text_col, date_col, temporal) in model_configs.items():
            # validate against the staged candidate (not yet promoted to latest/)
            model_path = settings.MODELS_DIR / f"bertopic_{model_type}" / "staging" / "model"
            if not model_path.exists():
                logger.warning(f"  {model_type}: staged model not found at {model_path} — skipping")
                continue
            try:
                model = BERTopic.load(str(model_path))
                df = pd.read_parquet(data_path)

                if temporal and date_col and date_col in df.columns:
                    df = df.sort_values(date_col)
                else:
                    rng = np.random.default_rng(42)
                    df = df.iloc[rng.permutation(len(df))]

                split = int(len(df) * 0.8)
                holdout_df = df.iloc[split:].reset_index(drop=True)
                col = text_col if text_col in holdout_df.columns else holdout_df.columns[0]
                docs = holdout_df[col].astype(str).tolist()
                embeddings = np.array(holdout_df["embedding"].tolist()) if "embedding" in holdout_df.columns else None

                report = validator.validate_holdout(model, docs, embeddings)
                report["model_type"] = model_type
                reports[model_type] = report
                validator.save_report(report, f"{model_type}_holdout_validation.json")
                logger.info(f"  {model_type}: status={report['status']}, silhouette={report['metrics'].get('silhouette_score', 'N/A')}")
            except Exception as e:
                logger.warning(f"  {model_type}: holdout validation failed — {e}")
                reports[model_type] = {"status": "error", "error": str(e)}

        return reports

    try:
        holdout_reports, metrics["validate_candidates"] = timed(validate_candidates)
    except Exception as e:
        logger.warning(f"  candidate validation skipped: {e}")
        metrics["validate_candidates"] = 0

    # 13. bias gate on candidates
    step(13, "Bias gate — candidates")

    bias_gate_results = {}

    def bias_gate_candidates():
        import numpy as np
        from bias_detection.holdout_bias_gate import HoldoutBiasGate

        gate = HoldoutBiasGate()
        results = {}

        for model_type, report in holdout_reports.items():
            if report.get("status") == "error":
                continue
            try:
                if model_type == "journals":
                    df = pd.read_parquet(jour_emb_path)
                    if "entry_date" in df.columns:
                        df = df.sort_values("entry_date")
                    split = int(len(df) * 0.8)
                    holdout_df = df.iloc[split:].reset_index(drop=True)
                else:
                    df = pd.read_parquet(conv_emb_path)
                    rng = np.random.default_rng(42)
                    indices = rng.permutation(len(df))
                    split = int(len(df) * 0.8)
                    holdout_df = df.iloc[indices[split:]].reset_index(drop=True)

                result = gate.evaluate(
                    holdout_df=holdout_df,
                    candidate_topics=report.get("holdout_topics", []),
                    candidate_probs=None,
                    num_topics=report.get("metrics", {}).get("num_topics", 0),
                )
                results[model_type] = result
                logger.info(f"  {model_type}: passed={result['passed']}, max_disparity={result['max_disparity_delta']}")
            except Exception as e:
                logger.warning(f"  {model_type}: bias gate failed — {e}")
                results[model_type] = {"passed": False, "error": str(e)}

        return results

    try:
        bias_gate_results, metrics["bias_gate_candidates"] = timed(bias_gate_candidates)
    except Exception as e:
        logger.warning(f"  bias gate skipped: {e}")
        metrics["bias_gate_candidates"] = 0

    # 14. selection decision + promotion
    step(14, "Selection decision + model promotion")

    def selection_and_promote():
        from topic_modeling.selection_policy import SelectionPolicy
        from topic_modeling.experiment_tracker import ExperimentTracker
        from topic_modeling.rollback import smoke_test_model
        from topic_modeling.config import promote_staging_to_latest, cleanup_staging
        from storage.mongodb_client import MongoDBClient

        policy = SelectionPolicy()
        decisions = {}
        promotion_results = {}
        any_promoted = False

        for model_type, candidate_report in holdout_reports.items():
            if candidate_report.get("status") == "error":
                decisions[model_type] = {"decision": "reject", "reasons": ["validation_error"]}
                continue
            bias_result = bias_gate_results.get(model_type)
            decision = policy.evaluate(
                candidate_report=candidate_report,
                active_report=None,
                bias_result=bias_result,
            )
            decisions[model_type] = decision
            logger.info(f"  {model_type}: {decision['decision']} — {decision['reasons']}")
            if decision["decision"] == "promote":
                any_promoted = True

        if not any_promoted:
            logger.warning("  no models promoted — keeping existing models")
            # clean up staging for all rejected models
            for model_type in decisions:
                cleanup_staging(model_type)
            return {"decisions": decisions, "promoted": {}}

        sample_docs = [
            "I feel anxious about work",
            "Had a productive therapy session today",
            "Struggling with sleep and depression",
        ]

        for model_type, decision in decisions.items():
            if decision.get("decision") != "promote":
                # rejected: clean up staging, keep existing latest/ untouched
                cleanup_staging(model_type)
                continue

            # smoke test uses the staging model path
            model_path = settings.MODELS_DIR / f"bertopic_{model_type}" / "staging" / "model"
            model_name = f"bertopic_{model_type}"

            smoke = smoke_test_model(model_name, str(model_path), sample_docs)
            if not smoke.get("passed", False):
                logger.error(f"  {model_type}: smoke test failed — {smoke}")
                promotion_results[model_type] = {"promoted": False, "reason": "smoke_test_failed"}
                cleanup_staging(model_type)
                continue

            # smoke test passed — promote staging → latest
            promote_staging_to_latest(model_type)
            latest_path = settings.MODELS_DIR / f"bertopic_{model_type}" / "latest" / "model"
            logger.info(f"  {model_type}: staging → latest promoted")

            tracker = ExperimentTracker(experiment_name=f"{model_type}_topic_model")
            resource_name = None
            if tracker.registry_enabled:
                # Vertex AI needs a GCS artifact URI — skip if no bucket configured
                if settings.MODEL_REGISTRY_BUCKET:
                    gcs_uri = f"gs://{settings.MODEL_REGISTRY_BUCKET}/{settings.MODEL_REGISTRY_PREFIX}/{model_type}/promoted/local_run"
                    resource_name = tracker.register_model(model_name, artifact_uri=gcs_uri)
                    if resource_name:
                        tracker.promote_to_production(model_name, resource_name)
                        logger.info(f"  {model_type}: promoted in Vertex AI: {resource_name}")
                else:
                    logger.info(f"  {model_type}: Vertex AI enabled but no GCS bucket — skipping registration")

            try:
                mongo = MongoDBClient()
                mongo.connect()
                try:
                    mongo.save_model_lifecycle_event({
                        "event_type": "promotion",
                        "model_name": model_name,
                        "resource_name": resource_name,
                        "model_path": str(latest_path),
                        "candidate_score": decision.get("candidate_score", 0),
                        "smoke_test": smoke,
                    })
                finally:
                    mongo.close()
            except Exception as e:
                logger.warning(f"  failed to log promotion event: {e}")

            promotion_results[model_type] = {"promoted": True, "resource_name": resource_name}

        return {"decisions": decisions, "promoted": promotion_results}

    try:
        lifecycle_result, metrics["selection_and_promote"] = timed(selection_and_promote)
        logger.info(f"  promoted: {lifecycle_result.get('promoted', {})}")
    except Exception as e:
        logger.warning(f"  selection/promotion skipped: {e}")
        metrics["selection_and_promote"] = 0

    # 15. store in mongodb
    step(15, "Store to MongoDB")
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()
        client.create_indexes()

        def store_all():
            conv_result = client.store_conversations_from_parquet(conv_emb_path)
            jour_result = client.store_journals_from_parquet(jour_emb_path)
            return {
                "conversations": conv_result,
                "journals": jour_result,
            }

        insert_results, metrics["store_to_mongodb"] = timed(store_all)
        logger.info(f"  insert results: {insert_results}")

        # classify conversations with bertopic topics + severity
        try:
            classify_result = client.classify_and_update_conversations()
            logger.info(f"  classification: {classify_result}")
        except Exception as ce:
            logger.warning(f"  conversation classification failed (non-fatal): {ce}")

        stats = client.get_collection_stats()
        logger.info(f"  collection stats: {stats}")

        # log the run to pipeline_metadata
        client.log_pipeline_run({
            "run_id": run_id,
            "run_date": datetime.now(timezone.utc).isoformat(),
            "metrics": {k: round(v, 2) for k, v in metrics.items()},
            "insert_results": insert_results,
            "collection_stats": stats,
        })
    finally:
        client.close()

    # 16. compute patient analytics
    step(16, "Compute patient analytics")

    def compute_analytics():
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        df = pd.read_parquet(
            settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
        )
        patient_ids = df["patient_id"].unique().tolist()

        analytics_client = MongoDBClient()
        try:
            analytics_client.connect()
            for pid in patient_ids:
                patient_df = df[df["patient_id"] == pid]
                journals = patient_df.to_dict(orient="records")
                analytics = pa.compute_patient_analytics(journals)
                analytics_client.upsert_patient_analytics(str(pid), analytics)
            return len(patient_ids)
        finally:
            analytics_client.close()

    try:
        patients_done, metrics["compute_analytics"] = timed(compute_analytics)
        logger.info(f"  analytics computed for {patients_done} patients")
    except Exception as e:
        logger.warning(f"  patient analytics failed (non-fatal): {e}")
        metrics["compute_analytics"] = 0

    # 17. upload model artifacts to GCS
    step(17, "Upload models to GCS")

    def upload_models_to_gcs():
        bucket_name = settings.MODEL_REGISTRY_BUCKET
        if not bucket_name:
            logger.warning("MODEL_REGISTRY_BUCKET not set — skipping GCS upload")
            return

        key_file = Path(settings.GCS_KEY_FILE)
        if not key_file.exists():
            logger.warning(f"GCS key file not found: {key_file} — skipping GCS upload")
            return

        # get promotion decisions from step 14
        decisions = {}
        try:
            decisions = lifecycle_result.get("decisions", {})
        except NameError:
            pass

        try:
            from google.cloud import storage as gcs

            client = gcs.Client.from_service_account_json(str(key_file))
            bucket = client.bucket(bucket_name)
            prefix = settings.MODEL_REGISTRY_PREFIX
            version_tag = datetime.now(timezone.utc).strftime("v_%Y%m%d_%H%M%S")

            # map model dir names to decision keys
            model_map = {
                "bertopic_journals": "journals",
                "bertopic_conversations": "conversations",
                "bertopic_severity": "severity",
            }
            total_uploaded = 0

            for model_type, decision_key in model_map.items():
                # promoted models are at latest/, rejected models were cleaned up (staging deleted)
                # upload from latest/ for promoted, skip rejected (already uploaded by step 14 if needed)
                decision = decisions.get(decision_key, {})
                status = "promoted" if decision.get("decision") == "promote" else "rejected"

                if status == "rejected":
                    # rejected models' staging was already cleaned up — nothing to upload
                    logger.info(f"  {model_type}: rejected — skipping GCS upload (no staging)")
                    continue

                model_dir = settings.MODELS_DIR / model_type / "latest" / "model"
                if not model_dir.exists():
                    logger.info(f"  {model_type}: not found at latest/, skipping")
                    continue

                files = [f for f in model_dir.rglob("*") if f.is_file()]
                for f in files:
                    rel = f.relative_to(model_dir)
                    # versioned copy under promoted/ (no latest/ on GCS)
                    bucket.blob(f"{prefix}/{model_type}/promoted/{version_tag}/{rel}").upload_from_filename(str(f))
                    total_uploaded += 1

                logger.info(f"  {model_type}: promoted/{version_tag}/ ({len(files)} files)")

            logger.info(f"  GCS upload complete: {total_uploaded} files → gs://{bucket_name}/{prefix}/")
        except Exception as e:
            logger.warning(f"GCS upload failed (non-blocking): {e}")

    _, metrics["upload_models_gcs"] = timed(upload_models_to_gcs)

    # summary
    total = sum(metrics.values())
    logger.info(f"\n{DIVIDER}\n  Pipeline Complete\n{DIVIDER}")
    logger.info("")
    for name, duration in metrics.items():
        m, s = divmod(int(duration), 60)
        fmt = f"{m}m {s}s" if m > 0 else f"{s}s"
        logger.info(f"  {name:<30s} {fmt:>10s}")
    m, s = divmod(int(total), 60)
    total_fmt = f"{m}m {s}s" if m > 0 else f"{s}s"
    logger.info(f"  {'─' * 42}")
    logger.info(f"  {'TOTAL':<30s} {total_fmt:>10s}")
    logger.info(f"\n  run_id: {run_id}")


if __name__ == "__main__":
    try:
        run()
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
