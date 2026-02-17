# tests for mongodb_client.py
# covers connection lifecycle, collection accessors, indexes, drop,
# insert_conversations, insert_journals, batch_insert, parquet loaders,
# pipeline metadata, collection stats, and the cli parser

import pytest
from unittest.mock import patch, Mock, MagicMock, PropertyMock
from pathlib import Path
import pandas as pd
import numpy as np

from pymongo.errors import BulkWriteError

from storage.mongodb_client import MongoDBClient, BATCH_SIZE, build_parser


# helpers
@pytest.fixture
def mock_mongo():
    """mock pymongo client + db + collections so nothing touches a real database"""
    with patch("storage.mongodb_client.MongoClient") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        # each collection is a fresh mock
        collections = {}
        def get_collection(name):
            if name not in collections:
                collections[name] = MagicMock()
                collections[name].insert_many.return_value = MagicMock(inserted_ids=["id1", "id2", "id3"])
                collections[name].count_documents.return_value = 42
            return collections[name]

        mock_db.__getitem__ = Mock(side_effect=get_collection)

        yield MockClient, mock_client, mock_db, collections


@pytest.fixture
def client(mock_settings, mock_mongo):
    c = MongoDBClient(uri="mongodb://test:27017", database="test_db")
    c.settings = mock_settings
    return c


# connection
class TestConnection:

    def test_connect_sets_db(self, client):
        db = client.connect()
        assert client.db is not None
        assert client.client is not None

    def test_connect_raises_when_no_uri(self, mock_settings):
        c = MongoDBClient(uri=None, database="test_db")
        c.settings = mock_settings
        c.settings.MONGODB_URI = None
        # manually set uri to None since constructor would have used settings
        c.uri = None
        with pytest.raises(ValueError, match="MONGODB_URI"):
            c.connect()

    def test_connect_returns_cached_db(self, client):
        db1 = client.connect()
        db2 = client.connect()
        # second call should reuse, not reconnect
        assert db1 is db2

    def test_close_clears_state(self, client):
        client.connect()
        client.close()
        assert client.client is None
        assert client.db is None


# collection accessors
class TestCollections:

    def test_rag_vectors_accessor(self, client):
        client.connect()
        coll = client.rag_vectors
        assert coll is not None

    def test_conversations_accessor(self, client):
        client.connect()
        coll = client.conversations
        assert coll is not None

    def test_journals_accessor(self, client):
        client.connect()
        coll = client.journals
        assert coll is not None

    def test_pipeline_metadata_accessor(self, client):
        client.connect()
        coll = client.pipeline_metadata
        assert coll is not None


# indexes
class TestCreateIndexes:

    def test_creates_indexes_without_error(self, client):
        client.connect()
        client.create_indexes()
        # just checking it doesn't blow up — the mocks absorb the calls


# drop collections
class TestDropCollections:

    def test_drops_all_collections(self, client, mock_mongo):
        _, _, mock_db, _ = mock_mongo
        client.connect()
        client.drop_collections()
        # should have called drop_collection for each collection name
        from storage.mongodb_client import COLLECTION_NAMES
        assert mock_db.drop_collection.call_count == len(COLLECTION_NAMES)


# insert_conversations
class TestInsertConversations:

    def test_inserts_to_rag_vectors_and_conversations(self, client, embedded_conversations_df):
        client.connect()
        result = client.insert_conversations(embedded_conversations_df)
        assert "rag_vectors" in result
        assert "conversations" in result
        # both should have inserted count > 0
        assert result["rag_vectors"] > 0
        assert result["conversations"] > 0

    def test_doc_structure_for_vectors(self, client, embedded_conversations_df):
        # hook into the batch insert to check what docs look like
        client.connect()
        inserted_docs = []
        original_batch = client._batch_insert

        def capture(collection, docs):
            inserted_docs.extend(docs)
            return len(docs)

        client._batch_insert = capture
        client.insert_conversations(embedded_conversations_df)

        # first half should be vector docs
        vec_doc = inserted_docs[0]
        assert vec_doc["doc_type"] == "conversation"
        assert "embedding" in vec_doc
        assert "metadata" in vec_doc

    def test_missing_columns_raises(self, client):
        # edge case: dataframe missing required columns
        bad_df = pd.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="Missing required columns"):
            client.insert_conversations(bad_df)


# insert_journals
class TestInsertJournals:

    def test_inserts_to_rag_vectors_and_journals(self, client, embedded_journals_df):
        client.connect()
        result = client.insert_journals(embedded_journals_df)
        assert "rag_vectors" in result
        assert "journals" in result
        assert result["rag_vectors"] > 0

    def test_null_date_handled(self, client):
        # edge case: entry_date is NaT
        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["some content"],
            "embedding": [[0.1] * 384],
            "embedding_text": ["text"],
        })
        df["entry_date"] = pd.NaT
        client.connect()
        result = client.insert_journals(df)
        assert result["journals"] > 0

    def test_missing_columns_raises(self, client):
        bad_df = pd.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="Missing required columns"):
            client.insert_journals(bad_df)


# batch insert
class TestBatchInsert:

    def test_splits_into_batches(self, client):
        client.connect()
        coll = MagicMock()
        coll.insert_many.return_value = MagicMock(inserted_ids=list(range(500)))

        # create more docs than BATCH_SIZE
        docs = [{"_id": i} for i in range(BATCH_SIZE + 100)]
        count = client._batch_insert(coll, docs)
        # should call insert_many twice (500 + 100)
        assert coll.insert_many.call_count == 2
        assert count > 0

    def test_handles_bulk_write_error(self, client):
        client.connect()
        coll = MagicMock()
        coll.insert_many.side_effect = BulkWriteError({"nInserted": 2, "writeErrors": [{"errmsg": "dup"}]})

        docs = [{"_id": i} for i in range(3)]
        count = client._batch_insert(coll, docs)
        assert count == 2

    def test_empty_list_returns_zero(self, client):
        client.connect()
        coll = MagicMock()
        count = client._batch_insert(coll, [])
        assert count == 0
        coll.insert_many.assert_not_called()


# parquet loaders
class TestParquetLoaders:

    def test_store_conversations_from_parquet(self, client, embedded_conversations_df, tmp_path):
        client.settings.PROCESSED_DATA_DIR = tmp_path
        path = tmp_path / "conversations" / "embedded_conversations.parquet"
        path.parent.mkdir(parents=True)
        embedded_conversations_df.to_parquet(path)

        with patch("storage.mongodb_client.config") as mc:
            mc.settings = client.settings
            client.connect()
            result = client.store_conversations_from_parquet(path)
            assert "rag_vectors" in result

    def test_missing_parquet_raises(self, client, tmp_path):
        with patch("storage.mongodb_client.config") as mc:
            mc.settings = client.settings
            mc.settings.PROCESSED_DATA_DIR = tmp_path
            with pytest.raises(FileNotFoundError):
                client.store_conversations_from_parquet(tmp_path / "nope.parquet")


# pipeline metadata
class TestPipelineMetadata:

    def test_log_pipeline_run(self, client):
        client.connect()
        client.log_pipeline_run({"run_id": "test-001", "status": "success"})
        # shouldn't raise — mock absorbs the insert_one call


# collection stats
class TestCollectionStats:

    def test_returns_all_collections(self, client):
        client.connect()
        stats = client.get_collection_stats()
        assert "rag_vectors" in stats
        assert "conversations" in stats
        assert "journals" in stats
        assert "pipeline_metadata" in stats


# cli parser
class TestBuildParser:

    def test_parser_has_subcommands(self):
        parser = build_parser()
        # parsing known subcommands should work
        args = parser.parse_args(["create-indexes"])
        assert args.command == "create-indexes"

        args = parser.parse_args(["stats"])
        assert args.command == "stats"

        args = parser.parse_args(["drop-collections"])
        assert args.command == "drop-collections"
