# tests for conversation_preprocessor.py
# covers column standardization, id generation, deduplication, text preprocessing,
# embedding text creation, validation filtering, load, and save

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from pathlib import Path

from preprocessing.conversation_preprocessor import ConversationPreprocessor


@pytest.fixture
def preprocessor(mock_settings):
    prep = ConversationPreprocessor()
    prep.settings = mock_settings
    return prep


# column standardization
class TestStandardizeColumns:

    def test_lowercases_column_names(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "Context": ["Q1", "Q2"],
            "Response": ["A1", "A2"],
            "QuestionTitle": ["T1", "T2"],
        })
        result = preprocessor.standardize_columns()

        assert "context" in result.columns
        assert "response" in result.columns
        assert "Context" not in result.columns

    def test_remaps_counsel_chat_columns(self, preprocessor):
        # the counsel-chat dataset uses questiontext/answertext instead of context/response
        preprocessor.df = pd.DataFrame({
            "questiontext": ["Q1"], "questiontitle": ["T1"], "answertext": ["A1"],
        })
        result = preprocessor.standardize_columns()

        assert "context" in result.columns
        assert "response" in result.columns
        assert "context_title" in result.columns


# id generation and deduplication
class TestGenerateIds:

    def test_assigns_unique_ids(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["Q1", "Q2"],
            "response": ["A1", "A2"],
        })
        result = preprocessor.generate_ids()

        assert "conversation_id" in result.columns
        assert len(result["conversation_id"].unique()) == 2

    def test_removes_duplicates(self, preprocessor):
        # same context+response → same md5 hash → gets deduped
        preprocessor.df = pd.DataFrame({
            "context": ["Q1", "Q2", "Q1"],
            "response": ["A1", "A2", "A1"],
        })
        result = preprocessor.generate_ids()
        assert len(result) == 2

    def test_keeps_different_responses_to_same_question(self, preprocessor):
        # counsel-chat has multiple answers per question — all should survive dedup
        preprocessor.df = pd.DataFrame({
            "context": ["Same question", "Same question", "Same question"],
            "response": ["Answer one", "Answer two", "Answer three"],
        })
        result = preprocessor.generate_ids()
        assert len(result) == 3


# text preprocessing
class TestApplyPreprocessing:

    def test_adds_all_stat_columns(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["Hello world today", "Test message here"],
            "response": ["Response one here", "Response two here"],
        })
        # use real BasePreprocessor instead of a mock — simpler and more realistic
        result = preprocessor.apply_preprocessing()

        expected_cols = [
            "context_word_count", "context_char_count", "context_sentence_count",
            "context_avg_word_length", "response_word_count", "response_char_count",
            "response_sentence_count", "response_avg_word_length", "is_embedded",
        ]
        for col in expected_cols:
            assert col in result.columns

    def test_sets_is_embedded_to_false(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["Hello"], "response": ["World"],
        })
        result = preprocessor.apply_preprocessing()
        assert result["is_embedded"].iloc[0] == False

    def test_strips_base64_data_uris(self, preprocessor):
        # real world case: some responses have embedded base64 images
        preprocessor.df = pd.DataFrame({
            "context": ["What helps with panic?"],
            "response": ['Try this: <img src="data:image/png;base64,iVBORw0KGgoAAAA" /> it works'],
        })
        result = preprocessor.apply_preprocessing()

        assert "base64" not in result["response"].iloc[0]
        assert "<DATA_URI>" in result["response"].iloc[0]
        # avg word length should be reasonable now
        assert result["response_avg_word_length"].iloc[0] < 30

    def test_handles_null_text(self, preprocessor):
        # edge case: null values in context/response should become empty strings, not crash
        preprocessor.df = pd.DataFrame({
            "context": [None, "Valid"], "response": ["Valid", None],
        })
        result = preprocessor.apply_preprocessing()
        assert len(result) == 2


# embedding text
class TestEmbeddingText:

    def test_creates_formatted_embedding_text(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["I need help"], "response": ["I can help you"],
        })
        result = preprocessor.create_embedding_text()

        assert "embedding_text" in result.columns
        assert "User concern:" in result["embedding_text"].iloc[0]
        assert "Counselor response:" in result["embedding_text"].iloc[0]


# validation
class TestValidation:

    def test_filters_out_empty_fields(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["Good question here", "", "Hi there"],
            "response": ["Good answer here", "Short answer", ""],
            "context_word_count": [3, 0, 2],
            "response_word_count": [3, 2, 0],
            "embedding_text": [
                "User concern: Good\n\nCounselor response: Good",
                "",
                "",
            ],
        })
        preprocessor.validate()

        # only first row has >= 3 words in both + non-empty embedding
        assert len(preprocessor.df) == 1
        assert preprocessor.df["context"].iloc[0] == "Good question here"

    def test_keeps_all_valid_rows(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "context": ["Good question", "Another question"],
            "response": ["Good answer", "Another answer"],
            "context_word_count": [5, 6],
            "response_word_count": [5, 6],
            "embedding_text": ["emb1", "emb2"],
        })
        result = preprocessor.validate()

        assert result is True
        assert len(preprocessor.df) == 2


# load and save
class TestLoadAndSave:

    @patch("preprocessing.conversation_preprocessor.pd.read_parquet")
    def test_loads_and_concatenates_parquet_files(self, mock_read, preprocessor, tmp_path):
        input_dir = tmp_path / "raw" / "conversations"
        input_dir.mkdir(parents=True)
        (input_dir / "f1.parquet").touch()
        (input_dir / "f2.parquet").touch()

        preprocessor.settings.RAW_DATA_DIR = tmp_path / "raw"
        mock_read.return_value = pd.DataFrame({"Context": ["Q1"], "Response": ["A1"]})

        result = preprocessor.load_data()

        assert len(result) == 2  # 2 files × 1 row each
        assert "source_file" in result.columns

    def test_saves_parquet_to_output_dir(self, preprocessor, tmp_path):
        preprocessor.df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        preprocessor.settings.PROCESSED_DATA_DIR = tmp_path

        path = preprocessor.save()

        assert path.exists()
        loaded = pd.read_parquet(path)
        assert len(loaded) == 2
