# shared fixtures for the entire test suite
# keeps individual test files short by centralising common setup

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest
import numpy as np
import pandas as pd

# make src/ and configs/ importable without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent))


# mock settings — used by almost every module
@pytest.fixture
def mock_settings(tmp_path):
    """minimal mock of configs.config.settings that points at tmp dirs"""
    s = Mock()
    s.RAW_DATA_DIR = tmp_path / "raw"
    s.PROCESSED_DATA_DIR = tmp_path / "processed"
    s.REPORTS_DIR = tmp_path / "reports"
    s.CONFIGS_DIR = tmp_path / "configs"
    s.LOGS_DIR = tmp_path / "logs"
    s.EMBEDDINGS_DIR = tmp_path / "embeddings"
    s.PROJECT_ROOT = tmp_path
    s.GEMINI_API_KEY = "test-key"
    s.GEMINI_MODEL = "gemini-test"
    s.EMBEDDING_MODEL = "test-model"
    s.MONGODB_URI = "mongodb://localhost:27017"
    s.MONGODB_DATABASE = "test_db"
    s.INCOMING_JOURNAL_MIN_LENGTH = 10
    s.INCOMING_JOURNAL_MAX_LENGTH = 10000
    s.INCOMING_JOURNAL_BATCH_INTERVAL = "*/30 * * * *"
    s.ensure_directories = Mock()
    return s


# sample dataframes — realistic-ish data for each pipeline stage
@pytest.fixture
def conversations_df():
    """basic conversations dataframe used across preprocessor, validator, bias tests"""
    return pd.DataFrame({
        "conversation_id": ["c1", "c2", "c3", "c4"],
        "context": [
            "I feel anxious and worried about work",
            "My depression is terrible and I can't cope",
            "Had a fight with my partner",
            "I want to kill myself",
        ],
        "response": [
            "It sounds like you are experiencing anxiety",
            "I hear how difficult this is for you",
            "Relationship conflicts can be very stressful",
            "I want to make sure you are safe right now",
        ],
        "response_word_count": [50, 60, 55, 100],
    })


@pytest.fixture
def conversations_processed_df():
    """fully processed conversations with all columns present"""
    return pd.DataFrame({
        "conversation_id": ["c1", "c2", "c3"],
        "context": ["Question one here", "Question two here", "Question three here"],
        "response": ["Answer one here ok", "Answer two here ok", "Answer three here ok"],
        "embedding_text": ["Emb text 1", "Emb text 2", "Emb text 3"],
        "context_word_count": [5, 10, 8],
        "context_char_count": [30, 40, 35],
        "context_sentence_count": [1, 2, 1],
        "context_avg_word_length": [5.0, 4.5, 4.8],
        "response_word_count": [8, 12, 10],
        "response_char_count": [40, 50, 45],
        "response_sentence_count": [1, 2, 2],
        "response_avg_word_length": [4.5, 4.2, 4.7],
    })


@pytest.fixture
def journals_df():
    """basic journals dataframe with a few patients"""
    return pd.DataFrame({
        "journal_id": ["j1", "j2", "j3", "j4", "j5"],
        "patient_id": ["p1", "p1", "p2", "p2", "p3"],
        "content": [
            "Feeling anxious about tomorrow",
            "Had a good day today",
            "Depressed and struggling",
            "Therapy session was helpful",
            "Work is stressful",
        ],
        "entry_date": ["2025-01-01", "2025-01-03", "2025-01-02", "2025-01-04", "2025-01-05"],
        "word_count": [20, 15, 18, 22, 16],
        "day_of_week": [0, 1, 2, 3, 4],
        "month": [1, 1, 2, 2, 3],
        "days_since_last": [0, 3, 0, 5, 0],
    })


@pytest.fixture
def journals_processed_df():
    """fully processed journals with all validator-required columns"""
    return pd.DataFrame({
        "journal_id": ["j1", "j2", "j3"],
        "patient_id": ["p1", "p1", "p2"],
        "therapist_id": ["t1", "t1", "t1"],
        "entry_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
        "content": ["Entry 1", "Entry 2", "Entry 3"],
        "embedding_text": ["[2025-01-01] Entry 1", "[2025-01-02] Entry 2", "[2025-01-03] Entry 3"],
        "word_count": [15, 20, 18],
        "char_count": [80, 100, 90],
        "sentence_count": [2, 3, 2],
        "avg_word_length": [4.5, 5.0, 4.8],
        "day_of_week": [2, 3, 4],
        "week_number": [1, 1, 1],
        "month": [1, 1, 1],
        "year": [2025, 2025, 2025],
        "days_since_last": [0, 1, 0],
    })


@pytest.fixture
def embedded_conversations_df():
    """conversations with embedding vectors attached — ready for storage"""
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
        "context_sentence_count": [1, 1, 2],
        "context_avg_word_length": [5.0, 5.0, 4.5],
        "response_word_count": [7, 8, 6],
        "response_char_count": [40, 41, 47],
        "response_sentence_count": [1, 1, 1],
        "response_avg_word_length": [5.5, 5.0, 7.5],
        "embedding_model": ["test-model"] * 3,
        "embedding_dim": [384] * 3,
        "is_embedded": [True] * 3,
    })


@pytest.fixture
def embedded_journals_df():
    """journals with embedding vectors attached — ready for storage"""
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
        "avg_word_length": [4.3, 5.0, 4.5],
        "day_of_week": [5, 0, 3],
        "week_number": [2, 3, 3],
        "month": [1, 1, 1],
        "year": [2026, 2026, 2026],
        "days_since_last": [0, 2, 3],
        "embedding_model": ["test-model"] * 3,
        "embedding_dim": [384] * 3,
        "is_embedded": [True] * 3,
    })


# helpers for embedding tests
FAKE_DIM = 384

def make_fake_model(dim=FAKE_DIM):
    """returns a mock SentenceTransformer that produces random embeddings"""
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = dim

    def _encode(sentences, **kwargs):
        return np.random.randn(len(sentences), dim).astype(np.float32)

    model.encode = MagicMock(side_effect=_encode)
    return model


@pytest.fixture
def embedding_service():
    """pre-configured EmbeddingService with a fake model"""
    from embedding.embedder import EmbeddingService

    service = EmbeddingService(model_name="test-model", batch_size=4)
    service.model = make_fake_model()
    service.embedding_dim = FAKE_DIM
    return service


# patient analytics fixtures
@pytest.fixture
def analytics():
    from analytics.patient_analytics import PatientAnalytics
    return PatientAnalytics()


@pytest.fixture
def sample_journals():
    return [
        {"content": "Feeling anxious and worried today", "entry_date": "2025-01-01"},
        {"content": "Had a good therapy session", "entry_date": "2025-01-03"},
        {"content": "Work stress is overwhelming", "entry_date": "2025-01-05"},
    ]