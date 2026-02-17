# tests for embedder.py
# covers EmbeddingService methods, embed_conversations, embed_journals,
# embed_incoming_journals, and _preprocess_journal_df

import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import time

import numpy as np
import pandas as pd

from embedding.embedder import (
    EmbeddingService,
    embed_conversations,
    embed_journals,
    embed_incoming_journals,
    _preprocess_journal_df,
    JOURNAL_EMBEDDING_SCHEMA,
)
from conftest import make_fake_model, FAKE_DIM


# EmbeddingService
class TestEmbeddingServiceInit:

    def test_model_not_loaded_initially(self, embedding_service):
        # model is injected by fixture, but a fresh one should start as None
        fresh = EmbeddingService(model_name="whatever")
        assert fresh.model is None
        assert fresh.embedding_dim is None


class TestEmbedTexts:

    def test_returns_correct_shape(self, embedding_service):
        texts = ["hello world", "another sentence", "one more"]
        result = embedding_service.embed_texts(texts)
        assert result.shape == (3, FAKE_DIM)

    def test_empty_list_returns_empty_array(self, embedding_service):
        result = embedding_service.embed_texts([])
        assert result.shape == (0, FAKE_DIM)

    def test_batching_calls_encode_multiple_times(self, embedding_service):
        # batch_size is 4, so 10 texts should cause 3 encode calls
        texts = [f"text {i}" for i in range(10)]
        embedding_service.embed_texts(texts)
        assert embedding_service.model.encode.call_count == 3


class TestEmbedDataframe:

    def test_adds_embedding_column(self, embedding_service):
        df = pd.DataFrame({"text": ["hello", "world"]})
        result = embedding_service.embed_dataframe(df, "text")
        assert "embedding" in result.columns
        assert len(result["embedding"].iloc[0]) == FAKE_DIM

    def test_missing_column_raises(self, embedding_service):
        df = pd.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="not found"):
            embedding_service.embed_dataframe(df, "nonexistent")


# embed_conversations
class TestEmbedConversations:

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_skips_existing_output(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROCESSED_DATA_DIR = tmp_path
        mock_config.settings.ensure_directories = Mock()

        output = tmp_path / "conversations" / "embedded_conversations.parquet"
        output.parent.mkdir(parents=True)
        output.touch()

        result = embed_conversations(skip_existing=True)
        assert result == output
        MockService.assert_not_called()

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_raises_when_input_missing(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROCESSED_DATA_DIR = tmp_path
        mock_config.settings.ensure_directories = Mock()

        with pytest.raises(FileNotFoundError):
            embed_conversations(skip_existing=False)

    @patch("embedding.embedder.config")
    def test_end_to_end(self, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROCESSED_DATA_DIR = tmp_path
        mock_config.settings.EMBEDDING_MODEL = "test-model"
        mock_config.settings.ensure_directories = Mock()

        # set up input
        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir(parents=True)
        input_df = pd.DataFrame({
            "conversation_id": ["c1", "c2"],
            "embedding_text": ["hello world", "another text"],
            "context": ["q1", "q2"],
            "response": ["a1", "a2"],
        })
        input_df.to_parquet(conv_dir / "processed_conversations.parquet")

        # patch the service to use fake model
        with patch("embedding.embedder.EmbeddingService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.model_name = "test-model"
            mock_svc.embedding_dim = FAKE_DIM

            def embed_df(df, text_column):
                df = df.copy()
                df["embedding"] = [[0.1] * FAKE_DIM] * len(df)
                return df

            mock_svc.embed_dataframe.side_effect = embed_df
            MockSvc.return_value = mock_svc

            result = embed_conversations(skip_existing=False)
            assert result.exists()


# embed_journals
class TestEmbedJournals:

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_skips_existing_output(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROCESSED_DATA_DIR = tmp_path
        mock_config.settings.ensure_directories = Mock()

        output = tmp_path / "journals" / "embedded_journals.parquet"
        output.parent.mkdir(parents=True)
        output.touch()

        result = embed_journals(skip_existing=True)
        assert result == output

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_raises_when_input_missing(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROCESSED_DATA_DIR = tmp_path
        mock_config.settings.ensure_directories = Mock()

        with pytest.raises(FileNotFoundError):
            embed_journals(skip_existing=False)


# _preprocess_journal_df
class TestPreprocessJournalDf:

    def test_computes_text_stats(self):
        df = pd.DataFrame({
            "content": ["Hello world today", "Another entry text here"],
            "patient_id": ["p1", "p1"],
            "entry_date": ["2025-01-01", "2025-01-03"],
        })
        result = _preprocess_journal_df(df)
        assert "word_count" in result.columns
        assert "char_count" in result.columns
        assert "sentence_count" in result.columns
        assert "embedding_text" in result.columns

    def test_temporal_features_added(self):
        df = pd.DataFrame({
            "content": ["entry one", "entry two"],
            "patient_id": ["p1", "p1"],
            "entry_date": ["2025-01-10", "2025-01-15"],
        })
        result = _preprocess_journal_df(df)
        assert "day_of_week" in result.columns
        assert "days_since_last" in result.columns
        assert result.iloc[1]["days_since_last"] == 5

    def test_handles_missing_dates(self):
        # edge case: no entry_date column at all
        df = pd.DataFrame({
            "content": ["some text"],
            "patient_id": ["p1"],
        })
        result = _preprocess_journal_df(df)
        assert "embedding_text" in result.columns


# embed_incoming_journals
class TestEmbedIncomingJournals:

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_basic_flow(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROJECT_ROOT = tmp_path

        mock_svc = MagicMock()
        mock_svc.model_name = "test-model"
        mock_svc.embedding_dim = FAKE_DIM

        def embed_df(df, text_column):
            df = df.copy()
            df["embedding"] = [[0.1] * FAKE_DIM] * len(df)
            return df

        mock_svc.embed_dataframe.side_effect = embed_df
        MockService.return_value = mock_svc

        journals = [
            {"journal_id": "j1", "patient_id": "p1", "content": "feeling better today", "entry_date": "2025-06-01"},
            {"journal_id": "j2", "patient_id": "p1", "content": "still working on it"},
        ]

        result = embed_incoming_journals(journals)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

        # verify output has the right schema
        for col in JOURNAL_EMBEDDING_SCHEMA:
            assert col in result.columns

    @patch("embedding.embedder.config")
    def test_missing_required_columns_raises(self, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROJECT_ROOT = tmp_path

        # missing patient_id
        with pytest.raises(ValueError, match="Missing required columns"):
            embed_incoming_journals([{"journal_id": "j1", "content": "text"}])

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_adds_default_therapist_id(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROJECT_ROOT = tmp_path

        mock_svc = MagicMock()
        mock_svc.model_name = "test-model"
        mock_svc.embedding_dim = FAKE_DIM

        def embed_df(df, text_column):
            df = df.copy()
            df["embedding"] = [[0.1] * FAKE_DIM] * len(df)
            return df

        mock_svc.embed_dataframe.side_effect = embed_df
        MockService.return_value = mock_svc

        journals = [{"journal_id": "j1", "patient_id": "p1", "content": "entry"}]

        result = embed_incoming_journals(journals)
        # therapist_id should be present but None
        assert "therapist_id" in result.columns

    @patch("embedding.embedder.config")
    @patch("embedding.embedder.EmbeddingService")
    def test_accepts_dataframe_input(self, MockService, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROJECT_ROOT = tmp_path

        mock_svc = MagicMock()
        mock_svc.model_name = "test-model"
        mock_svc.embedding_dim = FAKE_DIM

        def embed_df(df, text_column):
            df = df.copy()
            df["embedding"] = [[0.1] * FAKE_DIM] * len(df)
            return df

        mock_svc.embed_dataframe.side_effect = embed_df
        MockService.return_value = mock_svc

        df = pd.DataFrame({
            "journal_id": ["j1", "j2"],
            "patient_id": ["p1", "p1"],
            "content": ["entry one", "entry two"],
        })

        result = embed_incoming_journals(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch("embedding.embedder.config")
    def test_empty_list_returns_empty_df(self, mock_config, tmp_path):
        mock_config.settings = Mock()
        mock_config.settings.PROJECT_ROOT = tmp_path

        result = embed_incoming_journals([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
