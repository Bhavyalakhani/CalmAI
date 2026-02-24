# local incoming journals pipeline runner (no airflow)
# mirrors dag 2 exactly: fetch -> preprocess -> validate -> embed -> store ->
# conditional_retrain -> update_analytics -> mark_processed
# with timing for each step, edge case handling, and verification at the end
#
# usage:
#   python run_incoming_pipeline.py                    # run pipeline on existing unprocessed entries
#   python run_incoming_pipeline.py --seed             # seed test entries then run pipeline
#   python run_incoming_pipeline.py --seed-only        # seed test entries without running pipeline
#   python run_incoming_pipeline.py --force-retrain    # force retrain regardless of thresholds
#   python run_incoming_pipeline.py --verify-only      # just check db state, skip pipeline
#   python run_incoming_pipeline.py --skip-retrain     # skip the conditional retrain step

import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent / "src"))

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("incoming_pipeline")

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


# xcom simulation — mimics airflow's xcom push/pull for inter-task data passing

class XComStore:
    """simple dict-based xcom store for local execution."""

    def __init__(self):
        self._store = {}

    def push(self, task_id: str, key: str, value):
        self._store.setdefault(task_id, {})[key] = value

    def pull(self, task_id: str, key: str = None):
        task_data = self._store.get(task_id, {})
        if key is None:
            return task_data.get("return_value")
        return task_data.get(key)

    def summary(self):
        """print a compact summary of all xcom data."""
        for task_id, data in self._store.items():
            keys = list(data.keys())
            logger.info(f"  xcom[{task_id}]: {keys}")


# seed test data

def seed_test_entries(count: int = 5, force_retrain: bool = False):
    """insert test incoming journal entries into mongodb for pipeline testing.
    returns the number of entries seeded."""
    from storage.mongodb_client import MongoDBClient
    import hashlib

    client = MongoDBClient()
    try:
        client.connect()

        # use real patient ids from the seeded data
        patient_ids = [f"patient_{str(i).zfill(3)}" for i in range(1, 11)]

        # diverse test content covering various mental health journaling patterns
        # mood is an int 1-5 (1=very low, 5=very high) matching the backend JournalCreate schema
        test_entries = [
            {
                "content": "Today was a tough day at work. My manager criticized my presentation in front of everyone and I felt so embarrassed. I could not stop thinking about it on the drive home. Maybe I should have prepared more.",
                "patient_id": patient_ids[0],
                "mood": 2,
            },
            {
                "content": "I went for a long walk in the park this morning. The birds were singing and the air was fresh. It reminded me of childhood summers. For the first time in weeks I felt genuinely calm and present.",
                "patient_id": patient_ids[1],
                "mood": 4,
            },
            {
                "content": "I had an argument with my partner again about finances. We keep going in circles. I feel like we're stuck and I don't know how to break the pattern. It's exhausting.",
                "patient_id": patient_ids[2],
                "mood": 2,
            },
            {
                "content": "Therapy session went well today. We talked about setting boundaries with my family. I realized I've been saying yes to everything because I'm afraid of disappointing them. That's a pattern I want to change.",
                "patient_id": patient_ids[3],
                "mood": 4,
            },
            {
                "content": "Couldn't sleep last night. Kept replaying the conversation with my friend who said I was being selfish. Maybe they're right. I feel like I'm always letting people down no matter what I do.",
                "patient_id": patient_ids[4],
                "mood": 1,
            },
            {
                "content": "Started a new meditation practice this week. Only five minutes a day but it helps me notice when my thoughts are spiraling. Today I caught myself catastrophizing about a deadline and was able to step back.",
                "patient_id": patient_ids[0],
                "mood": 3,
            },
            {
                "content": "My anxiety has been really bad this week. I've been avoiding phone calls and canceling plans. I know isolation makes it worse but I just can't face people right now.",
                "patient_id": patient_ids[5],
                "mood": 1,
            },
            {
                "content": "Had a really good day today. Finished a project I've been putting off for months. The sense of accomplishment is amazing. I need to remember this feeling when I'm struggling with motivation.",
                "patient_id": patient_ids[6],
                "mood": 5,
            },
            {
                "content": "I've been thinking about my relationship with food lately. I notice I eat more when I'm stressed and then feel guilty about it. It's a cycle I want to understand better.",
                "patient_id": patient_ids[7],
                "mood": 3,
            },
            {
                "content": "Took my dog to the beach today. Watching him run through the waves made me smile for the first time all week. Sometimes simple things really do help. I'm grateful for these small moments.",
                "patient_id": patient_ids[8],
                "mood": 4,
            },
        ]

        # use requested count, cycling through entries if needed
        entries_to_seed = []
        for i in range(count):
            template = test_entries[i % len(test_entries)]
            timestamp = datetime.now(timezone.utc) - timedelta(hours=i * 2)
            content = template["content"]
            patient_id = template["patient_id"]

            # generate journal_id the same way the backend does
            hash_input = f"{patient_id}:{content}:{timestamp.isoformat()}"
            journal_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]

            entries_to_seed.append({
                "journal_id": journal_id,
                "patient_id": patient_id,
                "therapist_id": "therapist_001",
                "content": content,
                "entry_date": timestamp.isoformat(),
                "mood": template.get("mood"),
                "prompt_id": None,
                "is_processed": False,
            })

        # insert into incoming_journals collection
        if entries_to_seed:
            inserted = 0
            for entry in entries_to_seed:
                try:
                    client.incoming_journals.update_one(
                        {"journal_id": entry["journal_id"]},
                        {"$set": entry},
                        upsert=True,
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to seed entry {entry['journal_id']}: {e}")
            logger.info(f"Seeded {inserted} test entries into incoming_journals")

        # optionally manipulate training metadata to force retrain
        if force_retrain:
            old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            client.save_training_metadata({
                "journal_count": 0,
                "conversation_count": 0,
                "trained_at": old_date,
                "reason": "forced_stale_for_testing",
            })
            logger.info("Set training metadata to 10 days ago to force retrain")

        return len(entries_to_seed)
    finally:
        client.close()


# verification

def verify_db_state():
    """check the state of all relevant mongodb collections and print a report."""
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()

        print(f"\n{'=' * 70}")
        print("  DATABASE VERIFICATION REPORT")
        print(f"{'=' * 70}\n")

        # incoming_journals status
        total_incoming = client.incoming_journals.count_documents({})
        unprocessed = client.incoming_journals.count_documents({"is_processed": False})
        processed = client.incoming_journals.count_documents({"is_processed": True})
        print(f"incoming_journals:")
        print(f"  total: {total_incoming}")
        print(f"  processed: {processed}")
        print(f"  unprocessed: {unprocessed}")

        # journals collection
        total_journals = client.journals.count_documents({})
        embedded = client.journals.count_documents({"is_embedded": True})
        not_embedded = client.journals.count_documents({"is_embedded": {"$ne": True}})
        print(f"\njournals:")
        print(f"  total: {total_journals}")
        print(f"  embedded: {embedded}")
        print(f"  not embedded: {not_embedded}")

        # rag_vectors
        total_vectors = client.rag_vectors.count_documents({})
        journal_vectors = client.rag_vectors.count_documents({"doc_type": "journal"})
        conversation_vectors = client.rag_vectors.count_documents({"doc_type": "conversation"})
        print(f"\nrag_vectors:")
        print(f"  total: {total_vectors}")
        print(f"  journal vectors: {journal_vectors}")
        print(f"  conversation vectors: {conversation_vectors}")

        # conversations
        total_conversations = client.conversations.count_documents({})
        print(f"\nconversations:")
        print(f"  total: {total_conversations}")

        # patient_analytics
        total_analytics = client.patient_analytics.count_documents({})
        print(f"\npatient_analytics:")
        print(f"  total patients with analytics: {total_analytics}")

        # show per-patient analytics breakdown
        if total_analytics > 0:
            for doc in client.patient_analytics.find({}, {"patient_id": 1, "total_entries": 1, "computed_at": 1, "model_version": 1}):
                pid = doc.get("patient_id", "?")
                entries = doc.get("total_entries", 0)
                version = doc.get("model_version", "?")
                computed = doc.get("computed_at", "?")
                if isinstance(computed, str) and len(computed) > 19:
                    computed = computed[:19]
                print(f"    {pid}: {entries} entries, model={version}, computed={computed}")

        # training metadata
        last_training = client.get_last_training_metadata()
        print(f"\ntraining_metadata (latest):")
        if last_training:
            print(f"  journal_count: {last_training.get('journal_count', '?')}")
            print(f"  conversation_count: {last_training.get('conversation_count', '?')}")
            print(f"  trained_at: {last_training.get('trained_at', '?')}")
            print(f"  reason: {last_training.get('reason', '?')}")
            results = last_training.get("results")
            if results:
                for model_type, res in results.items():
                    if "error" in res:
                        print(f"    {model_type}: ERROR — {res['error']}")
                    else:
                        print(f"    {model_type}: {res.get('num_topics', '?')} topics, pass={res.get('quality_pass', '?')}")
        else:
            print("  (none found)")

        # sample recent incoming_journals
        print(f"\nrecent incoming_journals (last 5):")
        recent = list(client.incoming_journals.find().sort("entry_date", -1).limit(5))
        for doc in recent:
            jid = doc.get("journal_id", "?")
            pid = doc.get("patient_id", "?")
            processed_flag = doc.get("is_processed", "?")
            content_preview = str(doc.get("content", ""))[:60]
            print(f"  [{jid}] {pid} processed={processed_flag} — {content_preview}...")

        print(f"\n{'=' * 70}\n")
        return True
    finally:
        client.close()


# pipeline steps — mirror dag 2 callables exactly

def run(args):
    settings = config.settings

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    metrics = {}
    xcom = XComStore()

    logger.info(f"Incoming journal pipeline run: {run_id}")
    xcom.push("start", "run_id", run_id)

    # step 1: start
    step(1, "Initialize")
    logger.info(f"  run_id: {run_id}")
    logger.info(f"  retrain thresholds: entries={settings.RETRAIN_ENTRY_THRESHOLD}, days={settings.RETRAIN_MAX_DAYS}")
    metrics["start"] = 0

    # step 2: fetch unprocessed journals
    step(2, "Fetch unprocessed journals")

    def fetch_new_entries():
        from storage.mongodb_client import MongoDBClient

        client = MongoDBClient()
        try:
            client.connect()
            docs = client.fetch_unprocessed_journals()

            if not docs:
                logger.info("No unprocessed journals found — short-circuiting pipeline")
                xcom.push("fetch_new_entries", "journal_count", 0)
                return False

            # convert objectid to string for serialization (matches dag callable)
            serializable = []
            for doc in docs:
                doc["_id"] = str(doc.get("_id", ""))
                serializable.append(doc)

            xcom.push("fetch_new_entries", "incoming_journals", serializable)
            xcom.push("fetch_new_entries", "journal_count", len(serializable))
            logger.info(f"  fetched {len(serializable)} unprocessed journals")
            return True
        finally:
            client.close()

    has_entries, metrics["fetch_new_entries"] = timed(fetch_new_entries)

    if not has_entries:
        logger.info("\n" + DIVIDER)
        logger.info("  Pipeline short-circuited — no unprocessed entries")
        logger.info("  Use --seed to insert test entries first")
        logger.info(DIVIDER)
        return

    # step 3: preprocess
    step(3, "Preprocess entries")

    def preprocess_entries():
        journals = xcom.pull("fetch_new_entries", "incoming_journals")
        if not journals:
            logger.warning("No journals to preprocess")
            return

        from preprocessing.journal_preprocessor import process_incoming_journals
        records = process_incoming_journals(journals)
        xcom.push("preprocess_entries", "preprocessed_journals", records)
        xcom.push("preprocess_entries", "preprocessed_count", len(records))
        logger.info(f"  preprocessed {len(records)} entries")

    _, metrics["preprocess_entries"] = timed(preprocess_entries)

    # step 4: validate
    step(4, "Validate entries")

    def validate_entries():
        import pandas as pd
        from validation.schema_validator import SchemaValidator

        journals = xcom.pull("preprocess_entries", "preprocessed_journals")
        if journals is None:
            journals = xcom.pull("fetch_new_entries", "incoming_journals")

        if not journals:
            logger.warning("No journals to validate")
            return

        df = pd.DataFrame(journals)
        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)

        # log validation results
        passed = sum(1 for r in results if r.success)
        failed = [r for r in results if not r.success]
        logger.info(f"  validation: {passed}/{len(results)} checks passed")

        if failed:
            for r in failed:
                logger.warning(f"  FAILED: {r.name} — {r.details}")
            # filter empty content rows (matches dag callable behavior)
            if "content" in df.columns:
                original = len(df)
                df = df[df["content"].astype(str).str.strip().str.len() > 0]
                if len(df) < original:
                    logger.info(f"  filtered {original - len(df)} empty entries")

        valid_journals = df.to_dict("records")
        xcom.push("validate_entries", "valid_journals", valid_journals)
        xcom.push("validate_entries", "valid_count", len(valid_journals))
        logger.info(f"  {len(valid_journals)} valid journals")

    _, metrics["validate_entries"] = timed(validate_entries)

    # step 5: embed
    step(5, "Embed entries")

    def embed_entries():
        import pandas as pd
        journals = xcom.pull("validate_entries", "valid_journals")

        if not journals:
            logger.warning("No valid journals to embed")
            return

        from embedding.embedder import embed_incoming_journals
        embedded_df = embed_incoming_journals(journals)

        # create json-safe records (matches dag callable serialization)
        records = []
        for r in embedded_df.to_dict("records"):
            if "entry_date" in r and r["entry_date"] is not None:
                try:
                    if not isinstance(r["entry_date"], str):
                        r["entry_date"] = pd.Timestamp(r["entry_date"]).isoformat()
                except Exception:
                    pass
            records.append(r)

        xcom.push("embed_entries", "embedded_journals", records)
        logger.info(f"  embedded {len(records)} entries")

    _, metrics["embed_entries"] = timed(embed_entries)

    # step 6: store to mongodb
    step(6, "Store to MongoDB")

    def store_to_mongodb():
        import pandas as pd
        from storage.mongodb_client import MongoDBClient

        records = xcom.pull("embed_entries", "embedded_journals")
        if not records:
            logger.warning("No embedded journals to store")
            return

        df = pd.DataFrame(records)
        client = MongoDBClient()
        try:
            client.connect()
            result = client.insert_incoming_journals(df)
            xcom.push("store_to_mongodb", "insert_result", result)
            logger.info(f"  stored: {result}")
        finally:
            client.close()

    _, metrics["store_to_mongodb"] = timed(store_to_mongodb)

    # step 7: conditional retrain
    step(7, "Conditional retrain")

    if args.skip_retrain:
        logger.info("  --skip-retrain flag set, skipping conditional retrain step")
        metrics["conditional_retrain"] = 0
    else:
        def conditional_retrain():
            from storage.mongodb_client import MongoDBClient

            threshold_entries = settings.RETRAIN_ENTRY_THRESHOLD
            threshold_days = settings.RETRAIN_MAX_DAYS

            client = MongoDBClient()
            try:
                client.connect()

                current_journal_count = client.journals.count_documents({})
                current_conversation_count = client.conversations.count_documents({})

                last_training = client.get_last_training_metadata()

                should_retrain = False
                retrain_reason = ""

                if last_training is None:
                    logger.info("No training metadata found — saving baseline counts")
                    client.save_training_metadata({
                        "journal_count": current_journal_count,
                        "conversation_count": current_conversation_count,
                        "trained_at": datetime.now(timezone.utc).isoformat(),
                        "reason": "baseline",
                    })
                    xcom.push("conditional_retrain", "retrain_triggered", False)
                    xcom.push("conditional_retrain", "retrain_reason", "baseline metadata saved")
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
                        if isinstance(last_trained_at, str):
                            last_dt = datetime.fromisoformat(last_trained_at.replace("Z", "+00:00"))
                        else:
                            last_dt = last_trained_at
                        days_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
                        if days_since >= threshold_days:
                            should_retrain = True
                            retrain_reason = f"{days_since:.1f} days since last training (threshold: {threshold_days})"

                # force retrain override
                if args.force_retrain and not should_retrain:
                    should_retrain = True
                    retrain_reason = "forced via --force-retrain flag"

                if not should_retrain:
                    logger.info(f"  retrain not needed — {new_entries} new entries, thresholds not met")
                    xcom.push("conditional_retrain", "retrain_triggered", False)
                    xcom.push("conditional_retrain", "retrain_reason", "thresholds not met")
                    return

                logger.info(f"  retrain triggered: {retrain_reason}")

                # fetch full corpus from mongodb
                import pandas as pd
                all_journals = list(client.journals.find({}))
                all_conversations = list(client.conversations.find({}))

                journal_df = pd.DataFrame(all_journals) if all_journals else pd.DataFrame()
                conversation_df = pd.DataFrame(all_conversations) if all_conversations else pd.DataFrame()

                logger.info(f"  loaded {len(journal_df)} journals, {len(conversation_df)} conversations from MongoDB")

                from topic_modeling.config import TopicModelConfig
                from topic_modeling.trainer import TopicModelTrainer
                from topic_modeling.validation import TopicModelValidator

                retrain_results = {}

                # retrain journal model
                if len(journal_df) >= 20:
                    try:
                        cfg = TopicModelConfig(model_type="journals")
                        trainer = TopicModelTrainer(cfg)
                        docs, timestamps = trainer.prepare_journal_docs(journal_df)
                        result = trainer.train(docs, timestamps=timestamps)
                        model_path = trainer.save_model()

                        validator = TopicModelValidator(trainer.model, trainer.topics, docs)
                        quality = validator.validate_all()

                        retrain_results["journals"] = {
                            "num_topics": result["num_topics"],
                            "num_documents": result["num_documents"],
                            "outlier_ratio": result["outlier_ratio"],
                            "quality_pass": quality.get("overall_pass", False),
                            "model_path": str(model_path),
                        }
                        logger.info(f"  journal model: {result['num_topics']} topics from {len(docs)} docs")
                    except Exception as e:
                        logger.error(f"  journal model retrain failed: {e}")
                        retrain_results["journals"] = {"error": str(e)}
                else:
                    logger.info(f"  skipping journal model — only {len(journal_df)} docs (need 20+)")

                # retrain conversation model
                if len(conversation_df) >= 20:
                    try:
                        cfg = TopicModelConfig(model_type="conversations")
                        trainer = TopicModelTrainer(cfg)
                        docs, _ = trainer.prepare_conversation_docs(conversation_df)
                        result = trainer.train(docs)
                        model_path = trainer.save_model()

                        validator = TopicModelValidator(trainer.model, trainer.topics, docs)
                        quality = validator.validate_all()

                        retrain_results["conversations"] = {
                            "num_topics": result["num_topics"],
                            "num_documents": result["num_documents"],
                            "outlier_ratio": result["outlier_ratio"],
                            "quality_pass": quality.get("overall_pass", False),
                            "model_path": str(model_path),
                        }
                        logger.info(f"  conversation model: {result['num_topics']} topics from {len(docs)} docs")
                    except Exception as e:
                        logger.error(f"  conversation model retrain failed: {e}")
                        retrain_results["conversations"] = {"error": str(e)}
                else:
                    logger.info(f"  skipping conversation model — only {len(conversation_df)} docs (need 20+)")

                # retrain severity model
                if len(conversation_df) >= 20:
                    try:
                        cfg = TopicModelConfig(model_type="severity")
                        trainer = TopicModelTrainer(cfg)
                        docs, _ = trainer.prepare_conversation_docs(conversation_df)
                        result = trainer.train(docs)
                        model_path = trainer.save_model()

                        validator = TopicModelValidator(trainer.model, trainer.topics, docs)
                        quality = validator.validate_all()

                        retrain_results["severity"] = {
                            "num_topics": result["num_topics"],
                            "num_documents": result["num_documents"],
                            "outlier_ratio": result["outlier_ratio"],
                            "quality_pass": quality.get("overall_pass", False),
                            "model_path": str(model_path),
                        }
                        logger.info(f"  severity model: {result['num_topics']} topics from {len(docs)} docs")
                    except Exception as e:
                        logger.error(f"  severity model retrain failed: {e}")
                        retrain_results["severity"] = {"error": str(e)}
                else:
                    logger.info(f"  skipping severity model — only {len(conversation_df)} docs (need 20+)")

                # save new training metadata
                client.save_training_metadata({
                    "journal_count": current_journal_count,
                    "conversation_count": current_conversation_count,
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                    "reason": retrain_reason,
                    "results": retrain_results,
                })

                xcom.push("conditional_retrain", "retrain_triggered", True)
                xcom.push("conditional_retrain", "retrain_reason", retrain_reason)
                xcom.push("conditional_retrain", "retrain_results", retrain_results)
                logger.info(f"  retrain complete: {retrain_reason}")

            except Exception as e:
                logger.error(f"  conditional retrain failed: {e}")
                xcom.push("conditional_retrain", "retrain_triggered", False)
                xcom.push("conditional_retrain", "retrain_reason", f"error: {e}")
                raise
            finally:
                client.close()

        _, metrics["conditional_retrain"] = timed(conditional_retrain)

    # step 8: update patient analytics
    step(8, "Update patient analytics")

    def update_analytics():
        import pandas as pd
        from storage.mongodb_client import MongoDBClient
        from analytics.patient_analytics import PatientAnalytics

        records = xcom.pull("embed_entries", "embedded_journals")
        if not records:
            logger.warning("No journals — skipping analytics update")
            return

        df = pd.DataFrame(records)
        patient_ids = df["patient_id"].dropna().unique().tolist()
        logger.info(f"  updating analytics for {len(patient_ids)} patients: {patient_ids}")

        analytics_service = PatientAnalytics()
        client = MongoDBClient()
        try:
            client.connect()

            for pid in patient_ids:
                all_journals = list(client.journals.find({"patient_id": pid}))
                if all_journals:
                    analytics = analytics_service.compute_patient_analytics(all_journals)
                    client.upsert_patient_analytics(pid, analytics)
                    logger.info(f"    {pid}: {analytics['total_entries']} entries, model={analytics.get('model_version', '?')}")
                else:
                    logger.warning(f"    {pid}: no journals found in db")

            xcom.push("update_analytics", "patients_updated", len(patient_ids))
            logger.info(f"  analytics updated for {len(patient_ids)} patients")
        finally:
            client.close()

    _, metrics["update_analytics"] = timed(update_analytics)

    # step 9: mark processed
    step(9, "Mark journals processed")

    def mark_processed():
        from storage.mongodb_client import MongoDBClient

        journals = xcom.pull("fetch_new_entries", "incoming_journals")
        if not journals:
            logger.warning("No journals to mark as processed")
            return

        journal_ids = [j["journal_id"] for j in journals if "journal_id" in j]
        client = MongoDBClient()
        try:
            client.connect()
            client.mark_journals_processed(journal_ids)
            logger.info(f"  marked {len(journal_ids)} journals as processed")
        finally:
            client.close()

    _, metrics["mark_processed"] = timed(mark_processed)

    # step 10: summary + verification
    step(10, "Pipeline summary")

    total_time = sum(metrics.values())
    logger.info(f"\n  Pipeline completed in {total_time:.1f}s")
    logger.info(f"  Run ID: {run_id}")
    logger.info(f"\n  Step durations:")
    for task_name, duration in metrics.items():
        logger.info(f"    {task_name}: {duration:.1f}s")

    logger.info(f"\n  XCom store contents:")
    xcom.summary()

    # run verification
    logger.info("\n  Running database verification...")
    verify_db_state()


def main():
    parser = argparse.ArgumentParser(
        description="Local incoming journals pipeline runner (mirrors DAG 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python run_incoming_pipeline.py --seed           # seed 5 test entries, then run pipeline
  python run_incoming_pipeline.py --seed --count 20  # seed 20 entries, then run
  python run_incoming_pipeline.py --seed --force-retrain  # seed + force model retrain
  python run_incoming_pipeline.py --verify-only    # just check db state
  python run_incoming_pipeline.py --seed-only      # seed without running pipeline
  python run_incoming_pipeline.py --skip-retrain   # run pipeline without retrain step
        """,
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="Seed test incoming journal entries before running the pipeline",
    )
    parser.add_argument(
        "--seed-only", action="store_true",
        help="Only seed test entries, do not run the pipeline",
    )
    parser.add_argument(
        "--count", type=int, default=5,
        help="Number of test entries to seed (default: 5)",
    )
    parser.add_argument(
        "--force-retrain", action="store_true",
        help="Force retrain regardless of threshold checks",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only run database verification, skip the pipeline",
    )
    parser.add_argument(
        "--skip-retrain", action="store_true",
        help="Skip the conditional retrain step",
    )

    args = parser.parse_args()

    # verify-only mode
    if args.verify_only:
        logger.info("Running database verification only...")
        verify_db_state()
        return

    # seed mode
    if args.seed or args.seed_only:
        logger.info(f"Seeding {args.count} test incoming journal entries...")
        seeded = seed_test_entries(count=args.count, force_retrain=args.force_retrain)
        logger.info(f"Seeded {seeded} entries")

        if args.seed_only:
            logger.info("Seed-only mode — skipping pipeline run")
            verify_db_state()
            return

    # run the pipeline
    run(args)


if __name__ == "__main__":
    main()
