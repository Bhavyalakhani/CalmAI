import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
from pymongo.errors import BulkWriteError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.mongodb_client import MongoDBClient, BATCH_SIZE, COLLECTION_NAMES, build_parser


@pytest.fixture
def mock_mongo_client():
    with patch("storage.mongodb_client.MongoClient") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        mock_db = MagicMock()
        mock_instance.__getitem__ = MagicMock(return_value=mock_db)

        mock_collections = {}
        def get_collection(name):
            if name not in mock_collections:
                coll = MagicMock()
                coll.insert_many = MagicMock(
                    return_value=MagicMock(inserted_ids=list(range(10)))
                )
                coll.count_documents = MagicMock(return_value=42)
                coll.create_indexes = MagicMock()
                mock_collections[name] = coll
            return mock_collections[name]

        mock_db.__getitem__ = MagicMock(side_effect=get_collection)
        mock_db.drop_collection = MagicMock()

        for name in COLLECTION_NAMES:
            get_collection(name)

        client = MongoDBClient(uri="mongodb://localhost:27017", database="test_db")
        client.connect()

        yield client, mock_collections, mock_db


@pytest.fixture
def sample_conversation_df():
    return pd.DataFrame({
        "conversation_id": ["c1", "c2", "c3"],
        "context": [
            "I feel very anxious lately.",
            "My sleep has been terrible.",
            "I had a fight with my partner.",
        ],
        "response": [
            "It sounds like anxiety is impacting you.",
            "Poor sleep can affect many areas of life.",
            "Relationship conflicts are common stress sources.",
        ],
        "context_title": ["Anxiety", "Sleep", "Relationships"],
        "source_file": ["file1", "file1", "file2"],
        "embedding_text": [
            "User concern: I feel very anxious lately.\n\nCounselor response: It sounds like anxiety is impacting you.",
            "User concern: My sleep has been terrible.\n\nCounselor response: Poor sleep can affect many areas of life.",
            "User concern: I had a fight with my partner.\n\nCounselor response: Relationship conflicts are common stress sources.",
        ],
        "embedding": [[0.1] * 384, [0.2] * 384, [0.3] * 384],
        "context_word_count": [5, 5, 7],
        "context_char_count": [27, 27, 30],
        "response_word_count": [7, 8, 6],
        "response_char_count": [40, 41, 47],
        "embedding_model": ["test-model"] * 3,
        "embedding_dim": [384] * 3,
        "is_embedded": [True] * 3,
    })


@pytest.fixture
def sample_journal_df():
    return pd.DataFrame({
        "journal_id": ["j1", "j2", "j3"],
        "patient_id": ["p1", "p1", "p1"],
        "therapist_id": ["t1", "t1", "t1"],
        "entry_date": pd.to_datetime(["2026-01-10", "2026-01-12", "2026-01-15"]),
        "content": [
            "Today was a tough day at work.",
            "I practiced deep breathing exercises.",
            "Had a productive therapy session.",
        ],
        "embedding_text": [
            "[2026-01-10] Today was a tough day at work.",
            "[2026-01-12] I practiced deep breathing exercises.",
            "[2026-01-15] Had a productive therapy session.",
        ],
        "embedding": [[0.1] * 384, [0.2] * 384, [0.3] * 384],
        "word_count": [7, 5, 5],
        "char_count": [30, 36, 31],
        "sentence_count": [1, 1, 1],
        "day_of_week": [5, 0, 3],
        "week_number": [2, 3, 3],
        "month": [1, 1, 1],
        "year": [2026, 2026, 2026],
        "days_since_last": [0, 2, 3],
        "embedding_model": ["test-model"] * 3,
        "embedding_dim": [384] * 3,
        "is_embedded": [True] * 3,
    })


class TestMongoDBClientConnection:

    def test_connect_missing_uri(self):
        client = MongoDBClient(uri="", database="test_db")
        with pytest.raises(ValueError, match="MONGODB_URI is not set"):
            client.connect()

    @patch("storage.mongodb_client.MongoClient")
    def test_connect_success(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.__getitem__ = MagicMock(return_value=MagicMock())

        client = MongoDBClient(uri="mongodb://localhost:27017", database="test_db")
        db = client.connect()
        assert db is not None
        mock_instance.admin.command.assert_called_once_with("ping")

    @patch("storage.mongodb_client.MongoClient")
    def test_connect_cached(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.__getitem__ = MagicMock(return_value=MagicMock())

        client = MongoDBClient(uri="mongodb://localhost:27017", database="test_db")
        db1 = client.connect()
        db2 = client.connect()
        assert db1 is db2
        assert mock_cls.call_count == 1

    @patch("storage.mongodb_client.MongoClient")
    def test_close(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.__getitem__ = MagicMock(return_value=MagicMock())

        client = MongoDBClient(uri="mongodb://localhost:27017", database="test_db")
        client.connect()
        client.close()
        mock_instance.close.assert_called_once()
        assert client.client is None
        assert client.db is None


class TestCollectionAccessors:

    def test_rag_vectors(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = client.rag_vectors
        assert coll is not None

    def test_conversations(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = client.conversations
        assert coll is not None

    def test_journals(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = client.journals
        assert coll is not None

    def test_pipeline_metadata(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = client.pipeline_metadata
        assert coll is not None


class TestCreateIndexes:

    def test_create_indexes(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        client.create_indexes()
        assert collections["rag_vectors"].create_indexes.called
        assert collections["conversations"].create_indexes.called
        assert collections["journals"].create_indexes.called


class TestDropCollections:

    def test_drop_collections(self, mock_mongo_client):
        client, collections, mock_db = mock_mongo_client
        client.drop_collections()
        assert mock_db.drop_collection.call_count == len(COLLECTION_NAMES)
        for name in COLLECTION_NAMES:
            mock_db.drop_collection.assert_any_call(name)


class TestInsertConversations:

    def test_insert_conversations(self, mock_mongo_client, sample_conversation_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["conversations"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        result = client.insert_conversations(sample_conversation_df)

        assert result["rag_vectors"] == 3
        assert result["conversations"] == 3

    def test_insert_conversations_vector_doc_structure(self, mock_mongo_client, sample_conversation_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["conversations"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        client.insert_conversations(sample_conversation_df)

        call_args = collections["rag_vectors"].insert_many.call_args[0][0]
        doc = call_args[0]
        assert doc["doc_type"] == "conversation"
        assert doc["conversation_id"] == "c1"
        assert "embedding" in doc
        assert "content" in doc
        assert doc["metadata"]["original_context"] == "I feel very anxious lately."
        assert doc["metadata"]["original_response"] == "It sounds like anxiety is impacting you."

    def test_insert_conversations_raw_doc_structure(self, mock_mongo_client, sample_conversation_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["conversations"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        client.insert_conversations(sample_conversation_df)

        call_args = collections["conversations"].insert_many.call_args[0][0]
        doc = call_args[0]
        expected_keys = {
            "conversation_id", "context", "response", "context_title", "source_file",
            "context_word_count", "context_char_count", "response_word_count",
            "response_char_count", "embedding_text", "is_embedded",
        }
        assert set(doc.keys()) == expected_keys
        assert doc["conversation_id"] == "c1"
        assert doc["context"] == "I feel very anxious lately."
        assert doc["response"] == "It sounds like anxiety is impacting you."
        assert doc["context_title"] == "Anxiety"
        assert doc["source_file"] == "file1"
        assert doc["context_word_count"] == 5
        assert doc["context_char_count"] == 27
        assert doc["response_word_count"] == 7
        assert doc["response_char_count"] == 40
        assert doc["is_embedded"] is True

    def test_insert_conversations_missing_columns(self, mock_mongo_client):
        client, _, _ = mock_mongo_client
        df = pd.DataFrame({"some_col": [1]})
        with pytest.raises(ValueError, match="Missing required columns"):
            client.insert_conversations(df)

    def test_insert_conversations_empty_df(self, mock_mongo_client):
        client, _, _ = mock_mongo_client
        df = pd.DataFrame({
            "conversation_id": [],
            "embedding": [],
            "embedding_text": [],
        })
        result = client.insert_conversations(df)
        assert result["rag_vectors"] == 0
        assert result["conversations"] == 0


class TestInsertJournals:

    def test_insert_journals(self, mock_mongo_client, sample_journal_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        result = client.insert_journals(sample_journal_df)

        assert result["rag_vectors"] == 3
        assert result["journals"] == 3

    def test_insert_journals_vector_doc_structure(self, mock_mongo_client, sample_journal_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        client.insert_journals(sample_journal_df)

        call_args = collections["rag_vectors"].insert_many.call_args[0][0]
        doc = call_args[0]
        assert doc["doc_type"] == "journal"
        assert doc["journal_id"] == "j1"
        assert doc["patient_id"] == "p1"
        assert doc["therapist_id"] == "t1"
        assert "embedding" in doc
        assert doc["metadata"]["entry_date"] is not None

    def test_insert_journals_raw_doc_structure(self, mock_mongo_client, sample_journal_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        client.insert_journals(sample_journal_df)

        call_args = collections["journals"].insert_many.call_args[0][0]
        doc = call_args[0]
        expected_keys = {
            "journal_id", "patient_id", "therapist_id", "entry_date", "content",
            "word_count", "char_count", "sentence_count",
            "day_of_week", "week_number", "month", "year", "days_since_last",
            "embedding_text", "is_embedded",
        }
        assert set(doc.keys()) == expected_keys
        assert doc["journal_id"] == "j1"
        assert doc["patient_id"] == "p1"
        assert doc["therapist_id"] == "t1"
        assert doc["content"] == "Today was a tough day at work."
        assert doc["word_count"] == 7
        assert doc["char_count"] == 30
        assert doc["sentence_count"] == 1
        assert doc["day_of_week"] == 5
        assert doc["week_number"] == 2
        assert doc["month"] == 1
        assert doc["year"] == 2026
        assert doc["days_since_last"] == 0
        assert doc["is_embedded"] is True

    def test_insert_journals_missing_columns(self, mock_mongo_client):
        client, _, _ = mock_mongo_client
        df = pd.DataFrame({"some_col": [1]})
        with pytest.raises(ValueError, match="Missing required columns"):
            client.insert_journals(df)

    def test_insert_journals_null_date(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["b"])

        df = pd.DataFrame({
            "journal_id": ["j99"],
            "patient_id": ["p1"],
            "content": ["No date."],
            "embedding": [[0.1] * 384],
            "entry_date": [pd.NaT],
        })
        result = client.insert_journals(df)
        call_args = collections["rag_vectors"].insert_many.call_args[0][0]
        assert call_args[0]["metadata"]["entry_date"] is None


class TestBatchInsert:

    def test_batch_insert_splits_correctly(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = collections["rag_vectors"]
        coll.insert_many.return_value = MagicMock(inserted_ids=list(range(BATCH_SIZE)))

        docs = [{"i": i} for i in range(BATCH_SIZE * 2 + 10)]
        count = client._batch_insert(coll, docs)

        assert coll.insert_many.call_count == 3
        assert count > 0

    def test_batch_insert_handles_bulk_write_error(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        coll = collections["rag_vectors"]
        coll.insert_many.side_effect = BulkWriteError({"nInserted": 2, "writeErrors": [{"errmsg": "dup"}]})

        docs = [{"i": i} for i in range(5)]
        count = client._batch_insert(coll, docs)
        assert count == 2

    def test_batch_insert_empty(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        count = client._batch_insert(collections["rag_vectors"], [])
        assert count == 0


class TestParquetLoaders:

    def test_store_conversations_from_parquet(self, mock_mongo_client, tmp_path, sample_conversation_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["conversations"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        path = tmp_path / "embedded_conversations.parquet"
        sample_conversation_df.to_parquet(path, index=False)

        result = client.store_conversations_from_parquet(path)
        assert result["rag_vectors"] == 3
        assert result["conversations"] == 3

    def test_store_conversations_from_parquet_missing(self, mock_mongo_client, tmp_path):
        client, _, _ = mock_mongo_client
        with pytest.raises(FileNotFoundError):
            client.store_conversations_from_parquet(tmp_path / "missing.parquet")

    def test_store_journals_from_parquet(self, mock_mongo_client, tmp_path, sample_journal_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        path = tmp_path / "embedded_journals.parquet"
        sample_journal_df.to_parquet(path, index=False)

        result = client.store_journals_from_parquet(path)
        assert result["rag_vectors"] == 3
        assert result["journals"] == 3

    def test_store_journals_from_parquet_missing(self, mock_mongo_client, tmp_path):
        client, _, _ = mock_mongo_client
        with pytest.raises(FileNotFoundError):
            client.store_journals_from_parquet(tmp_path / "missing.parquet")

    def test_store_incoming_journals_from_parquet(self, mock_mongo_client, tmp_path, sample_journal_df):
        client, collections, _ = mock_mongo_client
        collections["rag_vectors"].insert_many.return_value = MagicMock(inserted_ids=["a", "b", "c"])
        collections["journals"].insert_many.return_value = MagicMock(inserted_ids=["d", "e", "f"])

        path = tmp_path / "incoming_20260211_120000.parquet"
        sample_journal_df.to_parquet(path, index=False)

        result = client.store_incoming_journals_from_parquet(path)
        assert result["rag_vectors"] == 3
        assert result["journals"] == 3


class TestPipelineMetadata:

    def test_log_pipeline_run(self, mock_mongo_client):
        client, collections, _ = mock_mongo_client
        run_data = {"run_id": "test-001", "status": "success"}
        client.log_pipeline_run(run_data)
        collections["pipeline_metadata"].insert_one.assert_called_once_with(run_data)


class TestCollectionStats:

    def test_get_collection_stats(self, mock_mongo_client):
        client, _, _ = mock_mongo_client
        stats = client.get_collection_stats()
        assert "rag_vectors" in stats
        assert "conversations" in stats
        assert "journals" in stats
        assert "pipeline_metadata" in stats
        assert all(isinstance(v, int) for v in stats.values())


class TestBuildParser:

    def test_parse_create_indexes(self):
        parser = build_parser()
        args = parser.parse_args(["create-indexes"])
        assert args.command == "create-indexes"

    def test_parse_drop_collections(self):
        parser = build_parser()
        args = parser.parse_args(["drop-collections"])
        assert args.command == "drop-collections"

    def test_parse_stats(self):
        parser = build_parser()
        args = parser.parse_args(["stats"])
        assert args.command == "stats"

    def test_parse_no_command(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
