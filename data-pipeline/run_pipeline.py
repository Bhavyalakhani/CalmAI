# local pipeline runner (no airflow)
# mirrors the full dag: acquire -> preprocess -> validate -> bias -> embed -> store
# with timing for each step and a validation gate that halts on failure

import sys
import time
import logging
from pathlib import Path
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
TOTAL_STEPS = 10


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

    # 9. store in mongodb
    step(9, "Store to MongoDB")
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

    # 10. dvc version tracking
    step(10, "DVC version tracking")
    import subprocess

    def dvc_version():
        try:
            dvc_root = str(settings.PROJECT_ROOT)

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
