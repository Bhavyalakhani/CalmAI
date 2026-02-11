import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embedding.embedder import EmbeddingService, embed_conversations, embed_journals, embed_incoming_journals, JOURNAL_EMBEDDING_SCHEMA

FAKE_DIM = 384


def _make_fake_model(dim: int = FAKE_DIM):
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = dim

    def _encode(sentences, **kwargs):
        return np.random.randn(len(sentences), dim).astype(np.float32)

    model.encode = MagicMock(side_effect=_encode)
    return model


@pytest.fixture
def embedding_service():
    service = EmbeddingService(model_name="test-model", batch_size=4)
    service.model = _make_fake_model()
    service.embedding_dim = FAKE_DIM
    return service


@pytest.fixture
def sample_texts():
    return [
        "I feel anxious about my upcoming exam.",
        "My relationship with my partner has been improving.",
        "I had a panic attack at work today.",
        "Therapy sessions have been really helpful lately.",
        "I am struggling with sleep issues.",
        "Feeling grateful for small wins this week.",
    ]


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
        "embedding_text": [
            "User concern: I feel very anxious lately.\n\nCounselor response: It sounds like anxiety is impacting you.",
            "User concern: My sleep has been terrible.\n\nCounselor response: Poor sleep can affect many areas of life.",
            "User concern: I had a fight with my partner.\n\nCounselor response: Relationship conflicts are common stress sources.",
        ],
    })


@pytest.fixture
def sample_journal_df():
    return pd.DataFrame({
        "journal_id": ["j1", "j2", "j3"],
        "patient_id": ["p1", "p1", "p1"],
        "content": [
            "Today was a tough day at work.",
            "I practiced deep breathing exercises.",
            "Had a productive therapy session.",
        ],
        "entry_date": pd.to_datetime(["2026-01-10", "2026-01-12", "2026-01-15"]),
        "embedding_text": [
            "[2026-01-10] Today was a tough day at work.",
            "[2026-01-12] I practiced deep breathing exercises.",
            "[2026-01-15] Had a productive therapy session.",
        ],
    })


class TestEmbeddingService:

    def test_load_model_sets_dimension(self):
        with patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model()):
            service = EmbeddingService(model_name="test-model")
            service.load_model()
            assert service.embedding_dim == FAKE_DIM
            assert service.model is not None

    def test_load_model_cached(self, embedding_service):
        model_ref = embedding_service.model
        embedding_service.load_model()
        assert embedding_service.model is model_ref

    def test_embed_texts_shape(self, embedding_service, sample_texts):
        result = embedding_service.embed_texts(sample_texts)
        assert result.shape == (len(sample_texts), FAKE_DIM)

    def test_embed_texts_empty(self, embedding_service):
        result = embedding_service.embed_texts([])
        assert result.shape == (0, FAKE_DIM)

    def test_embed_texts_batching(self, embedding_service):
        texts = [f"Text {i}" for i in range(10)]
        embedding_service.embed_texts(texts)
        assert embedding_service.model.encode.call_count == 3

    def test_embed_dataframe(self, embedding_service, sample_conversation_df):
        result = embedding_service.embed_dataframe(
            sample_conversation_df, text_column="embedding_text"
        )
        assert "embedding" in result.columns
        assert len(result) == len(sample_conversation_df)
        assert len(result["embedding"].iloc[0]) == FAKE_DIM

    def test_embed_dataframe_missing_column(self, embedding_service, sample_conversation_df):
        with pytest.raises(ValueError, match="not found"):
            embedding_service.embed_dataframe(
                sample_conversation_df, text_column="nonexistent"
            )

    def test_embed_dataframe_does_not_mutate(self, embedding_service, sample_conversation_df):
        original_cols = list(sample_conversation_df.columns)
        embedding_service.embed_dataframe(
            sample_conversation_df, text_column="embedding_text"
        )
        assert list(sample_conversation_df.columns) == original_cols


class TestConvenienceFunctions:

    def test_embed_conversations_skip_existing(self, tmp_path):
        output = tmp_path / "embedded_conversations.parquet"
        output.touch()
        result = embed_conversations(output_path=output, skip_existing=True, force=False)
        assert result == output

    def test_embed_conversations_missing_input(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Processed conversation data not found"):
            embed_conversations(
                input_path=tmp_path / "nonexistent.parquet",
                output_path=tmp_path / "output.parquet",
                skip_existing=False,
            )

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_conversations_end_to_end(self, mock_st, tmp_path, sample_conversation_df):
        input_path = tmp_path / "processed_conversations.parquet"
        output_path = tmp_path / "embedded_conversations.parquet"
        sample_conversation_df.to_parquet(input_path, index=False)

        result = embed_conversations(input_path=input_path, output_path=output_path, skip_existing=False)

        assert result == output_path
        assert output_path.exists()
        df = pd.read_parquet(output_path)
        assert "embedding" in df.columns
        assert "embedding_model" in df.columns
        assert "is_embedded" in df.columns
        assert df["is_embedded"].all()

    def test_embed_journals_skip_existing(self, tmp_path):
        output = tmp_path / "embedded_journals.parquet"
        output.touch()
        result = embed_journals(output_path=output, skip_existing=True, force=False)
        assert result == output

    def test_embed_journals_missing_input(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Processed journal data not found"):
            embed_journals(
                input_path=tmp_path / "nonexistent.parquet",
                output_path=tmp_path / "output.parquet",
                skip_existing=False,
            )

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_journals_end_to_end(self, mock_st, tmp_path, sample_journal_df):
        input_path = tmp_path / "processed_journals.parquet"
        output_path = tmp_path / "embedded_journals.parquet"
        sample_journal_df.to_parquet(input_path, index=False)

        result = embed_journals(input_path=input_path, output_path=output_path, skip_existing=False)

        assert result == output_path
        assert output_path.exists()
        df = pd.read_parquet(output_path)
        assert "embedding" in df.columns
        assert "embedding_model" in df.columns
        assert "embedding_dim" in df.columns
        assert "is_embedded" in df.columns
        assert len(df) == len(sample_journal_df)

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_conversations_force_regenerate(self, mock_st, tmp_path, sample_conversation_df):
        input_path = tmp_path / "processed_conversations.parquet"
        output_path = tmp_path / "embedded_conversations.parquet"
        sample_conversation_df.to_parquet(input_path, index=False)
        output_path.write_text("stale")

        embed_conversations(input_path=input_path, output_path=output_path, force=True)

        df = pd.read_parquet(output_path)
        assert "embedding" in df.columns


class TestEmbedIncomingJournals:

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_schema_matches_synthetic(self, mock_st, tmp_path, sample_journal_df):
        input_path = tmp_path / "processed_journals.parquet"
        output_path = tmp_path / "embedded_journals.parquet"
        sample_journal_df.to_parquet(input_path, index=False)
        embed_journals(input_path=input_path, output_path=output_path, skip_existing=False)
        synthetic_df = pd.read_parquet(output_path)

        journals = [
            {"journal_id": "j10", "patient_id": "p1", "content": "Feeling better today.", "entry_date": "2026-01-10"},
        ]
        incoming_path = embed_incoming_journals(journals, output_dir=tmp_path)
        incoming_df = pd.read_parquet(incoming_path)

        assert list(synthetic_df.columns) == list(incoming_df.columns)
        assert list(synthetic_df.columns) == JOURNAL_EMBEDDING_SCHEMA

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_basic(self, mock_st, tmp_path):
        journals = [
            {"journal_id": "j10", "patient_id": "p1", "content": "Feeling better today."},
            {"journal_id": "j11", "patient_id": "p1", "content": "Had a rough morning."},
        ]
        result = embed_incoming_journals(journals, output_dir=tmp_path)

        assert result.exists()
        assert result.parent == tmp_path
        df = pd.read_parquet(result)
        assert len(df) == 2
        assert list(df.columns) == JOURNAL_EMBEDDING_SCHEMA
        assert df["is_embedded"].all()
        assert df["word_count"].notnull().all()
        assert df["char_count"].notnull().all()
        assert df["sentence_count"].notnull().all()

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_with_dates(self, mock_st, tmp_path):
        journals = [
            {"journal_id": "j20", "patient_id": "p2", "content": "Good session.", "entry_date": "2026-02-01"},
            {"journal_id": "j21", "patient_id": "p2", "content": "Feeling anxious.", "entry_date": "2026-02-03"},
        ]
        result = embed_incoming_journals(journals, output_dir=tmp_path)

        df = pd.read_parquet(result)
        assert "[2026-02-01]" in df["embedding_text"].iloc[0]
        assert "[2026-02-03]" in df["embedding_text"].iloc[1]
        assert df["day_of_week"].notnull().all()
        assert df["month"].notnull().all()
        assert df["year"].notnull().all()
        assert df["days_since_last"].iloc[0] == 0
        assert df["days_since_last"].iloc[1] == 2

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_without_dates(self, mock_st, tmp_path):
        journals = [
            {"journal_id": "j30", "patient_id": "p3", "content": "No date entry."},
        ]
        result = embed_incoming_journals(journals, output_dir=tmp_path)

        df = pd.read_parquet(result)
        assert df["embedding_text"].iloc[0] == "No date entry."

    def test_embed_incoming_journals_missing_columns(self, tmp_path):
        journals = [{"content": "Missing patient_id and journal_id."}]
        with pytest.raises(ValueError, match="Missing required columns"):
            embed_incoming_journals(journals, output_dir=tmp_path)

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_unique_filenames(self, mock_st, tmp_path):
        journals = [{"journal_id": "j40", "patient_id": "p4", "content": "Entry."}]
        result1 = embed_incoming_journals(journals, output_dir=tmp_path)
        import time
        time.sleep(1.1)
        result2 = embed_incoming_journals(journals, output_dir=tmp_path)
        assert result1 != result2
        assert len(list(tmp_path.glob("incoming_*.parquet"))) == 2

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_therapist_id_default(self, mock_st, tmp_path):
        journals = [{"journal_id": "j50", "patient_id": "p5", "content": "Entry without therapist."}]
        result = embed_incoming_journals(journals, output_dir=tmp_path)
        df = pd.read_parquet(result)
        assert "therapist_id" in df.columns

    @patch("embedding.embedder.SentenceTransformer", return_value=_make_fake_model())
    def test_embed_incoming_journals_preprocesses_content(self, mock_st, tmp_path):
        journals = [{"journal_id": "j60", "patient_id": "p6", "content": "Visit  https://example.com  today"}]
        result = embed_incoming_journals(journals, output_dir=tmp_path)
        df = pd.read_parquet(result)
        assert "<URL>" in df["content"].iloc[0]
        assert "  " not in df["content"].iloc[0]
