import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from pymongo import MongoClient, IndexModel, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config  # pyright: ignore[reportMissingImports]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500

COLLECTION_NAMES = ["rag_vectors", "conversations", "journals", "pipeline_metadata"]


class MongoDBClient:

    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None):
        self.settings = config.settings
        self.uri = uri if uri is not None else self.settings.MONGODB_URI
        self.database_name = database if database is not None else self.settings.MONGODB_DATABASE
        self.client = None
        self.db = None

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
        ])

        self.journals.create_indexes([
            IndexModel([("journal_id", ASCENDING)], unique=True),
            IndexModel([("patient_id", ASCENDING)]),
            IndexModel([("therapist_id", ASCENDING)]),
        ])

        logger.info("Indexes created successfully")

    def drop_collections(self):
        self.connect()
        logger.info("Dropping all collections...")

        for name in COLLECTION_NAMES:
            self.db.drop_collection(name)
            logger.info(f"Dropped collection: {name}")

        logger.info("All collections dropped")

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

    def insert_conversations(self, df: pd.DataFrame) -> Dict[str, int]:
        self.connect()

        required = ["conversation_id", "embedding", "embedding_text"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

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

            raw_docs.append({
                "conversation_id": r["conversation_id"],
                "context": r.get("context", ""),
                "response": r.get("response", ""),
                "context_title": r.get("context_title", ""),
                "source_file": r.get("source_file", ""),
                "context_word_count": r.get("context_word_count", 0),
                "context_char_count": r.get("context_char_count", 0),
                "response_word_count": r.get("response_word_count", 0),
                "response_char_count": r.get("response_char_count", 0),
                "embedding_text": r.get("embedding_text", ""),
                "is_embedded": True,
            })

        logger.info(f"Inserting {len(df)} conversations into MongoDB...")
        vec_count = self._batch_insert(self.rag_vectors, vector_docs)
        raw_count = self._batch_insert(self.conversations, raw_docs)

        logger.info(f"Inserted {vec_count} vector docs, {raw_count} raw conversation docs")
        return {"rag_vectors": vec_count, "conversations": raw_count}

    def insert_journals(self, df: pd.DataFrame) -> Dict[str, int]:
        self.connect()

        required = ["journal_id", "patient_id", "embedding", "content"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

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

    def log_pipeline_run(self, run_data: Dict[str, Any]):
        self.connect()
        self.pipeline_metadata.insert_one(run_data)
        logger.info(f"Logged pipeline run: {run_data.get('run_id', 'unknown')}")

    def get_collection_stats(self) -> Dict[str, int]:
        self.connect()
        return {
            "rag_vectors": self.rag_vectors.count_documents({}),
            "conversations": self.conversations.count_documents({}),
            "journals": self.journals.count_documents({}),
            "pipeline_metadata": self.pipeline_metadata.count_documents({}),
        }


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
