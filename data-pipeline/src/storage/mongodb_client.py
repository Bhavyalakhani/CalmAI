# mongodb client for storing embedded data
# handles batch inserts (500 at a time), index creation,
# parquet loading, and pipeline metadata logging

import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from pymongo import MongoClient, IndexModel, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, OperationFailure
from pymongo.operations import SearchIndexModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500

# all collections the pipeline writes to
COLLECTION_NAMES = [
    "rag_vectors", "conversations", "journals", "pipeline_metadata",
    "incoming_journals", "patient_analytics",
]


class MongoDBClient:

    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None):
        self.settings = config.settings
        self.uri = uri if uri is not None else self.settings.MONGODB_URI
        self.database_name = database if database is not None else self.settings.MONGODB_DATABASE
        self.client = None
        self.db = None

    # connection lifecycle

    def connect(self) -> Database:
        if self.db is not None:
            return self.db

        if not self.uri:
            raise ValueError("MONGODB_URI is not set. Provide it via .env or constructor.")

        logger.info(f"Connecting to MongoDB database: {self.database_name}")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.database_name]
        self.client.admin.command("ping")
        logger.info("MongoDB connection established")
        return self.db

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")

    # collection accessors

    def get_collection(self, name: str) -> Collection:
        self.connect()
        return self.db[name]

    @property
    def rag_vectors(self) -> Collection:
        return self.get_collection("rag_vectors")

    @property
    def conversations(self) -> Collection:
        return self.get_collection("conversations")

    @property
    def journals(self) -> Collection:
        return self.get_collection("journals")

    @property
    def pipeline_metadata(self) -> Collection:
        return self.get_collection("pipeline_metadata")

    @property
    def incoming_journals(self) -> Collection:
        return self.get_collection("incoming_journals")

    @property
    def patient_analytics(self) -> Collection:
        return self.get_collection("patient_analytics")

    # index management

    def create_indexes(self):
        self.connect()
        logger.info("Creating indexes...")

        self.rag_vectors.create_indexes([
            IndexModel([("doc_type", ASCENDING)]),
            IndexModel([("patient_id", ASCENDING)]),
            IndexModel([("therapist_id", ASCENDING)]),
            IndexModel([("conversation_id", ASCENDING)]),
            IndexModel([("journal_id", ASCENDING)]),
        ])

        self.conversations.create_indexes([
            IndexModel([("conversation_id", ASCENDING)], unique=True),
            IndexModel([("topic", ASCENDING)]),
            IndexModel([("severity", ASCENDING)]),
        ])

        self.journals.create_indexes([
            IndexModel([("journal_id", ASCENDING)], unique=True),
            IndexModel([("patient_id", ASCENDING)]),
            IndexModel([("therapist_id", ASCENDING)]),
        ])

        self.incoming_journals.create_indexes([
            IndexModel([("journal_id", ASCENDING)], unique=True),
            IndexModel([("patient_id", ASCENDING)]),
            IndexModel([("is_processed", ASCENDING)]),
        ])

        self.patient_analytics.create_indexes([
            IndexModel([("patient_id", ASCENDING)], unique=True),
        ])

        # atlas vector search index on rag_vectors.embedding
        # this is idempotent — skips if the index already exists
        self._ensure_vector_search_index()

        logger.info("Indexes created successfully")

    def _ensure_vector_search_index(self):
        """create the atlas vector search index if it doesn't already exist.

        requires an M10+ atlas cluster (vector search is not available on
        shared/free tier). silently skips if the index exists or if the
        cluster doesn't support search indexes.
        """
        index_name = "vector_index"

        try:
            # check if the index already exists
            existing = list(self.rag_vectors.list_search_indexes())
            for idx in existing:
                if idx.get("name") == index_name:
                    logger.info(f"Vector search index '{index_name}' already exists, skipping")
                    return

            # create the index
            model = SearchIndexModel(
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": 384,
                            "similarity": "cosine",
                        },
                        {
                            "type": "filter",
                            "path": "patient_id",
                        },
                        {
                            "type": "filter",
                            "path": "doc_type",
                        },
                    ]
                },
                name=index_name,
                type="vectorSearch",
            )
            self.rag_vectors.create_search_index(model)
            logger.info(f"Vector search index '{index_name}' created — may take 1-2 min to become active")
        except OperationFailure as e:
            logger.warning(f"Could not create vector search index (cluster may not support it): {e}")
        except Exception as e:
            logger.warning(f"Vector search index creation skipped: {e}")

    def drop_collections(self):
        self.connect()
        logger.info("Dropping all collections...")

        for name in COLLECTION_NAMES:
            self.db.drop_collection(name)
            logger.info(f"Dropped collection: {name}")

        logger.info("All collections dropped")

    # batch insert with bulkwriteerror handling

    def _batch_insert(self, collection: Collection, documents: List[Dict[str, Any]]) -> int:
        if not documents:
            return 0

        total_inserted = 0
        for i in range(0, len(documents), BATCH_SIZE):
            batch = documents[i : i + BATCH_SIZE]
            try:
                result = collection.insert_many(batch, ordered=False)
                total_inserted += len(result.inserted_ids)
            except BulkWriteError as e:
                total_inserted += e.details.get("nInserted", 0)
                logger.warning(f"Batch insert partial failure: {e.details.get('writeErrors', [])[:3]}")

        return total_inserted

    # insert conversations (writes to both rag_vectors and conversations collections)

    def insert_conversations(self, df: pd.DataFrame) -> Dict[str, int]:
        self.connect()

        required = ["conversation_id", "embedding", "embedding_text"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # clear old conversation vectors to prevent duplicates across pipeline runs
        deleted = self.rag_vectors.delete_many({"doc_type": "conversation"})
        logger.info(f"Cleared {deleted.deleted_count} existing conversation vectors from rag_vectors")

        # clear old raw conversations too
        deleted_raw = self.conversations.delete_many({})
        logger.info(f"Cleared {deleted_raw.deleted_count} existing raw conversations")

        vector_docs = []
        raw_docs = []

        for _, row in df.iterrows():
            r = row.to_dict()

            embedding = r["embedding"]
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()

            vector_docs.append({
                "doc_type": "conversation",
                "conversation_id": r["conversation_id"],
                "content": r.get("embedding_text", ""),
                "embedding": embedding,
                "metadata": {
                    "conversation_id": r["conversation_id"],
                    "original_context": r.get("context", ""),
                    "original_response": r.get("response", ""),
                },
            })

            raw_doc = {
                "conversation_id": r["conversation_id"],
                "context": r.get("context", ""),
                "response": r.get("response", ""),
                "context_title": r.get("context_title", ""),
                "source_file": r.get("source_file", ""),
                "context_word_count": r.get("context_word_count", 0),
                "context_char_count": r.get("context_char_count", 0),
                "context_sentence_count": r.get("context_sentence_count", 0),
                "context_avg_word_length": r.get("context_avg_word_length", 0.0),
                "response_word_count": r.get("response_word_count", 0),
                "response_char_count": r.get("response_char_count", 0),
                "response_sentence_count": r.get("response_sentence_count", 0),
                "response_avg_word_length": r.get("response_avg_word_length", 0.0),
                "embedding_text": r.get("embedding_text", ""),
                "is_embedded": True,
            }
            # include topic/severity if present in the dataframe
            if "topic" in r and r["topic"] is not None:
                raw_doc["topic"] = r["topic"]
            if "severity" in r and r["severity"] is not None:
                raw_doc["severity"] = r["severity"]
            raw_docs.append(raw_doc)

        logger.info(f"Inserting {len(df)} conversations into MongoDB...")
        vec_count = self._batch_insert(self.rag_vectors, vector_docs)
        raw_count = self._batch_insert(self.conversations, raw_docs)

        logger.info(f"Inserted {vec_count} vector docs, {raw_count} raw conversation docs")
        return {"rag_vectors": vec_count, "conversations": raw_count}

    # insert journals (writes to both rag_vectors and journals collections)

    def insert_journals(self, df: pd.DataFrame) -> Dict[str, int]:
        self.connect()

        required = ["journal_id", "patient_id", "embedding", "content"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # clear old journal vectors to prevent duplicates across pipeline runs
        deleted = self.rag_vectors.delete_many({"doc_type": "journal"})
        logger.info(f"Cleared {deleted.deleted_count} existing journal vectors from rag_vectors")

        # clear old raw journals too
        deleted_raw = self.journals.delete_many({})
        logger.info(f"Cleared {deleted_raw.deleted_count} existing raw journals")

        vector_docs = []
        raw_docs = []

        for _, row in df.iterrows():
            r = row.to_dict()

            entry_date = r.get("entry_date")
            if pd.notna(entry_date):
                entry_date = pd.Timestamp(entry_date).isoformat()
            else:
                entry_date = None

            embedding = r["embedding"]
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()

            vector_docs.append({
                "doc_type": "journal",
                "journal_id": r["journal_id"],
                "patient_id": r["patient_id"],
                "therapist_id": r.get("therapist_id"),
                "content": r.get("embedding_text", r["content"]),
                "embedding": embedding,
                "metadata": {
                    "journal_id": r["journal_id"],
                    "patient_id": r["patient_id"],
                    "therapist_id": r.get("therapist_id"),
                    "entry_date": entry_date,
                },
            })

            raw_docs.append({
                "journal_id": r["journal_id"],
                "patient_id": r["patient_id"],
                "therapist_id": r.get("therapist_id"),
                "content": r["content"],
                "entry_date": entry_date,
                "word_count": r.get("word_count", 0),
                "char_count": r.get("char_count", 0),
                "sentence_count": r.get("sentence_count", 0),
                "avg_word_length": r.get("avg_word_length", 0.0),
                "day_of_week": r.get("day_of_week"),
                "week_number": r.get("week_number"),
                "month": r.get("month"),
                "year": r.get("year"),
                "days_since_last": r.get("days_since_last", 0),
                "embedding_text": r.get("embedding_text", ""),
                "is_embedded": True,
            })

        logger.info(f"Inserting {len(df)} journals into MongoDB...")
        vec_count = self._batch_insert(self.rag_vectors, vector_docs)
        raw_count = self._batch_insert(self.journals, raw_docs)

        logger.info(f"Inserted {vec_count} vector docs, {raw_count} raw journal docs")
        return {"rag_vectors": vec_count, "journals": raw_count}

    # parquet loaders — convenience methods that read parquet then insert

    def store_conversations_from_parquet(self, path: Optional[Path] = None) -> Dict[str, int]:
        settings = config.settings
        if path is None:
            path = settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"

        if not path.exists():
            raise FileNotFoundError(f"Embedded conversations not found: {path}")

        df = pd.read_parquet(path)
        logger.info(f"Loaded {len(df)} embedded conversations from {path}")
        return self.insert_conversations(df)

    def store_journals_from_parquet(self, path: Optional[Path] = None) -> Dict[str, int]:
        settings = config.settings
        if path is None:
            path = settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"

        if not path.exists():
            raise FileNotFoundError(f"Embedded journals not found: {path}")

        df = pd.read_parquet(path)
        logger.info(f"Loaded {len(df)} embedded journals from {path}")
        return self.insert_journals(df)

    def store_incoming_journals_from_parquet(self, path: Path) -> Dict[str, int]:
        if not path.exists():
            raise FileNotFoundError(f"Incoming journal embeddings not found: {path}")

        df = pd.read_parquet(path)
        logger.info(f"Loaded {len(df)} incoming journal embeddings from {path}")
        return self.insert_journals(df)

    # incoming journal staging — backend writes here, dag 2 reads from here

    def fetch_unprocessed_journals(self) -> List[Dict[str, Any]]:
        """fetch all journals from incoming_journals where is_processed is false"""
        self.connect()
        cursor = self.incoming_journals.find({"is_processed": False})
        docs = list(cursor)
        logger.info(f"Fetched {len(docs)} unprocessed incoming journals")
        return docs

    def mark_journals_processed(self, journal_ids: List[str]):
        """mark a batch of incoming journals as processed"""
        self.connect()
        if not journal_ids:
            return

        result = self.incoming_journals.update_many(
            {"journal_id": {"$in": journal_ids}},
            {"$set": {"is_processed": True}},
        )
        logger.info(f"Marked {result.modified_count} journals as processed")

    def insert_incoming_journals(self, df: pd.DataFrame) -> Dict[str, int]:
        """append incoming journals to rag_vectors and journals (no clear).
        uses upsert for journals to handle edits + retries without duplicates.
        deletes existing rag_vectors before inserting to prevent stale embeddings."""
        self.connect()

        required = ["journal_id", "patient_id", "embedding", "content"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        vector_docs = []
        raw_upsert_count = 0

        for _, row in df.iterrows():
            r = row.to_dict()

            entry_date = r.get("entry_date")
            if pd.notna(entry_date):
                entry_date = pd.Timestamp(entry_date).isoformat()
            else:
                entry_date = None

            embedding = r["embedding"]
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()

            vector_docs.append({
                "doc_type": "journal",
                "journal_id": r["journal_id"],
                "patient_id": r["patient_id"],
                "therapist_id": r.get("therapist_id"),
                "content": r.get("embedding_text", r["content"]),
                "embedding": embedding,
                "metadata": {
                    "journal_id": r["journal_id"],
                    "patient_id": r["patient_id"],
                    "therapist_id": r.get("therapist_id"),
                    "entry_date": entry_date,
                    "prompt_id": r.get("prompt_id"),
                    "mood": r.get("mood"),
                },
            })

            raw_doc = {
                "journal_id": r["journal_id"],
                "patient_id": r["patient_id"],
                "therapist_id": r.get("therapist_id"),
                "content": r["content"],
                "entry_date": entry_date,
                "word_count": r.get("word_count", 0),
                "char_count": r.get("char_count", 0),
                "sentence_count": r.get("sentence_count", 0),
                "avg_word_length": r.get("avg_word_length", 0.0),
                "day_of_week": r.get("day_of_week"),
                "week_number": r.get("week_number"),
                "month": r.get("month"),
                "year": r.get("year"),
                "days_since_last": r.get("days_since_last", 0),
                "embedding_text": r.get("embedding_text", ""),
                "is_embedded": True,
                "prompt_id": r.get("prompt_id"),
                "mood": r.get("mood"),
            }

            # upsert into journals to prevent duplicates on edits and retries
            try:
                self.journals.update_one(
                    {"journal_id": r["journal_id"]},
                    {"$set": raw_doc},
                    upsert=True,
                )
                raw_upsert_count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert journal {r['journal_id']}: {e}")

        # remove existing rag_vectors for these journals before re-inserting
        # (prevents duplicates on edits and dag retries)
        journal_ids = df["journal_id"].tolist()
        if journal_ids:
            self.rag_vectors.delete_many({
                "journal_id": {"$in": journal_ids},
                "doc_type": "journal",
            })

        logger.info(f"Appending {len(df)} incoming journals to MongoDB...")
        vec_count = self._batch_insert(self.rag_vectors, vector_docs)

        logger.info(f"Upserted {raw_upsert_count} journal docs, inserted {vec_count} vector docs")
        return {"rag_vectors": vec_count, "journals": raw_upsert_count}

    # conversation classification (topic + severity)

    @staticmethod
    def classify_severity(text: str) -> str:
        """classify severity using bertopic severity model.
        delegates to shared severity module."""
        from src.severity import classify_severity
        return classify_severity(text)

    def classify_and_update_conversations(self) -> Dict[str, int]:
        """classify all conversations with bertopic topics + bertopic severity.
        reads context from mongodb conversations collection, predicts topics
        using the trained conversation model, predicts severity using the
        trained severity model, then bulk-updates the mongodb documents."""
        self.connect()

        # load all conversation contexts
        docs = list(self.conversations.find({}, {"conversation_id": 1, "context": 1}))
        if not docs:
            logger.info("No conversations to classify")
            return {"classified": 0, "topic_updates": 0, "severity_updates": 0}

        logger.info(f"Classifying {len(docs)} conversations...")
        contexts = [d.get("context", "") for d in docs]

        # topic classification via bertopic
        try:
            from topic_modeling.inference import TopicModelInference
            inference = TopicModelInference(model_type="conversations")
            if not inference.load():
                raise RuntimeError("Conversation BERTopic model not available")

            topics, _ = inference.predict(contexts)
            topic_labels = [inference.get_topic_label(int(t)) for t in topics]
        except Exception as e:
            logger.error(f"Topic classification failed: {e}")
            raise

        # severity classification via bertopic severity model (batch)
        try:
            from src.severity import classify_severity_batch
            severities = classify_severity_batch(contexts)
        except Exception as e:
            logger.warning(f"Severity model classification failed: {e}")
            severities = ["unknown"] * len(contexts)

        topic_updates = 0
        severity_updates = 0

        from pymongo import UpdateOne
        operations = []

        for doc, topic_id, topic_label, severity in zip(docs, topics, topic_labels, severities):
            cid = doc["conversation_id"]

            update_fields = {}
            topic_id_int = int(topic_id)
            if topic_id_int != -1:
                update_fields["topic"] = topic_label
                topic_updates += 1
            else:
                update_fields["topic"] = "Other"
                topic_updates += 1

            update_fields["severity"] = severity
            severity_updates += 1

            operations.append(
                UpdateOne(
                    {"conversation_id": cid},
                    {"$set": update_fields},
                )
            )

        # execute in batches
        total_modified = 0
        for i in range(0, len(operations), BATCH_SIZE):
            batch = operations[i:i + BATCH_SIZE]
            result = self.conversations.bulk_write(batch, ordered=False)
            total_modified += result.modified_count

        logger.info(
            f"Classified {len(docs)} conversations: "
            f"{topic_updates} topic updates, {severity_updates} severity updates, "
            f"{total_modified} documents modified"
        )

        return {
            "classified": len(docs),
            "topic_updates": topic_updates,
            "severity_updates": severity_updates,
            "modified": total_modified,
        }

    def upsert_patient_analytics(self, patient_id: str, analytics: Dict[str, Any]):
        """upsert analytics data for a patient (topic dist, mood trends, etc.)"""
        self.connect()
        from datetime import datetime, timezone

        analytics["patient_id"] = patient_id
        analytics["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.patient_analytics.update_one(
            {"patient_id": patient_id},
            {"$set": analytics},
            upsert=True,
        )
        logger.info(f"Upserted analytics for patient {patient_id}")

    # pipeline metadata and stats

    def log_pipeline_run(self, run_data: Dict[str, Any]):
        self.connect()
        self.pipeline_metadata.insert_one(run_data)
        logger.info(f"Logged pipeline run: {run_data.get('run_id', 'unknown')}")

    def get_last_training_metadata(self) -> Optional[Dict[str, Any]]:
        """get the most recent training metadata from pipeline_metadata.
        returns None if no training has been recorded yet."""
        self.connect()
        doc = self.pipeline_metadata.find_one(
            {"type": "training_metadata"},
            sort=[("trained_at", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def save_training_metadata(self, metadata: Dict[str, Any]):
        """save training metadata (entry counts, timestamp) for conditional retrain checks"""
        self.connect()
        self.pipeline_metadata.insert_one({
            "type": "training_metadata",
            **metadata,
        })
        logger.info(f"Saved training metadata: journal_count={metadata.get('journal_count')}, "
                     f"conversation_count={metadata.get('conversation_count')}")

    def get_collection_stats(self) -> Dict[str, int]:
        self.connect()
        return {
            "rag_vectors": self.rag_vectors.count_documents({}),
            "conversations": self.conversations.count_documents({}),
            "journals": self.journals.count_documents({}),
            "pipeline_metadata": self.pipeline_metadata.count_documents({}),
            "incoming_journals": self.incoming_journals.count_documents({}),
            "patient_analytics": self.patient_analytics.count_documents({}),
        }


# cli for manual index/collection management

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mongodb_client")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("create-indexes")
    sub.add_parser("drop-collections")
    sub.add_parser("stats")

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = MongoDBClient()

    try:
        if args.command == "create-indexes":
            client.create_indexes()

        elif args.command == "drop-collections":
            client.drop_collections()

        elif args.command == "stats":
            stats = client.get_collection_stats()
            for name, count in stats.items():
                print(f"{name}: {count}")
    finally:
        client.close()
