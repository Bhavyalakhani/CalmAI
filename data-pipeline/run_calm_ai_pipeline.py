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
TOTAL_STEPS = 14


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

    logger.info("validation passed — continuing to bias analysis")

    # 6. bias analysis — conversations
    step(6, "Bias analysis — conversations")
    from bias_detection.conversation_bias import ConversationBiasAnalyzer

    def bias_conversations():
        report = ConversationBiasAnalyzer().run(skip_existing=False)
        if report and report.underrepresented_topics:
            logger.warning(f"  underrepresented topics (<3%): {report.underrepresented_topics}")
        return report

    _, metrics["bias_conversations"] = timed(bias_conversations)

    # 7. bias analysis — journals
    step(7, "Bias analysis — journals")
    from bias_detection.journal_bias import JournalBiasAnalyzer

    def bias_journals():
        report = JournalBiasAnalyzer().run(skip_existing=False)
        if report and report.sparse_patients:
            logger.warning(f"  sparse patients (<10 entries): {len(report.sparse_patients)}")
        return report

    _, metrics["bias_journals"] = timed(bias_journals)

    # 8. embed both datasets
    step(8, "Embed conversations + journals")
    from embedding.embedder import embed_conversations, embed_journals

    def run_embed_conversations():
        return embed_conversations(force=True)

    conv_emb_path, metrics["embed_conversations"] = timed(run_embed_conversations)
    logger.info(f"  conversations → {conv_emb_path}")

    def run_embed_journals():
        return embed_journals(force=True)

    jour_emb_path, metrics["embed_journals"] = timed(run_embed_journals)
    logger.info(f"  journals      → {jour_emb_path}")

    # 9. train journal topic model (requires bertopic / umap / hdbscan)
    step(9, "Train journal topic model")

    def train_journal_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="journals")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(jour_emb_path)
        docs, timestamps = trainer.prepare_journal_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        result = trainer.train(docs, embeddings=embeddings, timestamps=timestamps)
        model_path = trainer.save_model()
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

    # 10. train conversation topic model (requires bertopic / umap / hdbscan)
    step(10, "Train conversation topic model")

    def train_conversation_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="conversations")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(conv_emb_path)
        docs, _ = trainer.prepare_conversation_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        result = trainer.train(docs, embeddings=embeddings)
        model_path = trainer.save_model()
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

    # 11. train severity model (uses same conversation embeddings with severity prompt)
    step(11, "Train severity model")

    def train_severity_model():
        import pandas as pd
        import numpy as np
        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig
        from topic_modeling.validation import TopicModelValidator

        cfg = TopicModelConfig(model_type="severity")
        trainer = TopicModelTrainer(cfg)
        df = pd.read_parquet(conv_emb_path)
        docs, _ = trainer.prepare_conversation_docs(df)
        embeddings = np.array(df["embedding"].tolist()) if "embedding" in df.columns else None
        result = trainer.train(docs, embeddings=embeddings)
        model_path = trainer.save_model()
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

    # 12. store in mongodb
    step(12, "Store to MongoDB")
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

    # 13. compute patient analytics
    step(13, "Compute patient analytics")

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

    # 14. dvc version tracking
    step(14, "DVC version tracking")
    import subprocess

    def dvc_version():
        try:
            dvc_root = str(settings.PROJECT_ROOT.parent)

            # commit current artifact state to dvc.lock
            # (artifacts are already declared as outputs in dvc.yaml)
            result = subprocess.run(
                ["dvc", "commit", "--force"],
                cwd=dvc_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"DVC commit complete: {result.stdout.strip()}")
            else:
                logger.warning(f"DVC commit warning: {result.stderr.strip()}")

            # push to remote
            result = subprocess.run(
                ["dvc", "push"],
                cwd=dvc_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"DVC push complete: {result.stdout.strip()}")
            else:
                logger.warning(f"DVC push warning: {result.stderr.strip()}")
        except Exception as e:
            logger.warning(f"DVC step failed (non-blocking): {e}")

    _, metrics["dvc_version"] = timed(dvc_version)

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
