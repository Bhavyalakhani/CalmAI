import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent / "src"))

import config  # pyright: ignore[reportMissingImports]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("pipeline")

DIVIDER = "=" * 60


def step(name):
    logger.info(f"\n{DIVIDER}\n  {name}\n{DIVIDER}")


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

    # ---- 1. Preprocess conversations ----
    step("Step 1/4 — Preprocess conversations")
    from preprocessing.conversation_preprocessor import ConversationPreprocessor

    def preprocess_conversations():
        p = ConversationPreprocessor()
        return p.run(skip_existing=False)

    _, metrics["preprocess_conversations"] = timed(preprocess_conversations)

    # ---- 2. Preprocess journals ----
    step("Step 2/4 — Preprocess journals")
    from preprocessing.journal_preprocessor import JournalPreprocessor

    def preprocess_journals():
        p = JournalPreprocessor()
        return p.run(skip_existing=False)

    _, metrics["preprocess_journals"] = timed(preprocess_journals)

    # ---- 3. Embed both datasets ----
    step("Step 3/4 — Embed conversations + journals")
    from embedding.embedder import embed_conversations, embed_journals

    def run_embeddings():
        conv_path = embed_conversations(force=True)
        jour_path = embed_journals(force=True)
        return conv_path, jour_path

    (conv_emb_path, jour_emb_path), metrics["embedding"] = timed(run_embeddings)
    logger.info(f"  conversations → {conv_emb_path}")
    logger.info(f"  journals      → {jour_emb_path}")

    # ---- 4. Store in MongoDB ----
    step("Step 4/4 — Store in MongoDB")
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()
        client.create_indexes()

        def store_all():
            conv_result = client.store_conversations_from_parquet(conv_emb_path)
            jour_result = client.store_journals_from_parquet(jour_emb_path)
            return {
                "conversations_inserted": conv_result,
                "journals_inserted": jour_result,
            }

        insert_results, metrics["mongodb_insert"] = timed(store_all)
        logger.info(f"  {insert_results}")

        stats = client.get_collection_stats()
        logger.info(f"  Collection counts: {stats}")

        client.log_pipeline_run({
            "run_id": run_id,
            "run_date": datetime.now(timezone.utc).isoformat(),
            "metrics": {k: round(v, 2) for k, v in metrics.items()},
            "insert_results": insert_results,
            "collection_stats": stats,
        })
    finally:
        client.close()

    # ---- Summary ----
    total = sum(metrics.values())
    step("Pipeline Complete")
    for name, duration in metrics.items():
        logger.info(f"  {name:<30s} {duration:>7.1f}s")
    logger.info(f"  {'TOTAL':<30s} {total:>7.1f}s")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
