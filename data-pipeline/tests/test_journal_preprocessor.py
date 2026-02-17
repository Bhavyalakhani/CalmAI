# tests for journal_preprocessor.py
# covers date parsing, text preprocessing, temporal features,
# days_since_last calculation, embedding text, validation, and save

import pytest
from unittest.mock import Mock
import pandas as pd
from datetime import datetime

from preprocessing.journal_preprocessor import JournalPreprocessor


@pytest.fixture
def preprocessor(mock_settings):
    prep = JournalPreprocessor()
    prep.settings = mock_settings
    return prep


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "journal_id": ["j1", "j2", "j3"],
        "patient_id": ["p1", "p1", "p2"],
        "content": ["Feeling anxious today", "Had a good day", "Work stress"],
        "entry_date": ["2025-01-01", "2025-01-03", "2025-01-02"],
    })


# date parsing
class TestDateParsing:

    def test_converts_strings_to_datetime(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        result = preprocessor.parse_dates()

        assert pd.api.types.is_datetime64_any_dtype(result["entry_date"])
        assert result["entry_date"].iloc[0] == pd.Timestamp("2025-01-01")

    def test_forward_fills_invalid_dates(self, preprocessor):
        # edge case: some dates are garbage strings, should get filled from neighbors
        preprocessor.df = pd.DataFrame({
            "patient_id": ["p1", "p1", "p1"],
            "entry_date": ["2025-01-01", "not-a-date", "2025-01-03"]
        })
        result = preprocessor.parse_dates()

        # the invalid date should be forward-filled from the previous valid date
        assert pd.notna(result["entry_date"].iloc[1])
        assert result["entry_date"].iloc[1] == pd.Timestamp("2025-01-01")

    def test_handles_all_invalid_dates(self, preprocessor):
        # edge case: every single date is invalid, nothing to fill from
        preprocessor.df = pd.DataFrame({
            "patient_id": ["p1", "p1", "p1"],
            "entry_date": ["nope", "also nope", "still nope"]
        })
        result = preprocessor.parse_dates()
        assert result["entry_date"].isna().all()


# text preprocessing
class TestPreprocessing:

    def test_adds_stat_columns(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        result = preprocessor.apply_preprocessing()

        for col in ["word_count", "char_count", "sentence_count", "avg_word_length", "is_embedded"]:
            assert col in result.columns

    def test_sets_is_embedded_false(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        result = preprocessor.apply_preprocessing()
        assert (result["is_embedded"] == False).all()

    def test_handles_null_content(self, preprocessor):
        # edge case: null content should become empty string, not crash
        preprocessor.df = pd.DataFrame({
            "journal_id": ["j1"], "patient_id": ["p1"], "content": [None],
            "entry_date": ["2025-01-01"],
        })
        result = preprocessor.apply_preprocessing()
        assert result["word_count"].iloc[0] == 0


# temporal features
class TestTemporalFeatures:

    def test_adds_all_temporal_columns(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.add_temporal_features()

        for col in ["day_of_week", "month", "year"]:
            assert col in result.columns
        # jan 1 2025 is a wednesday = day 2
        assert result["month"].iloc[0] == 1
        assert result["year"].iloc[0] == 2025

    def test_skips_if_no_entry_date(self, preprocessor):
        # edge case: dataframe has no entry_date column at all
        preprocessor.df = pd.DataFrame({"content": ["test"]})
        result = preprocessor.add_temporal_features()
        assert "day_of_week" not in result.columns


# days since last
class TestDaysSinceLast:

    def test_first_entry_per_patient_is_zero(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.calculate_days_since_last()

        # first entry for each patient should be 0
        p1_first = result[result["patient_id"] == "p1"]["days_since_last"].iloc[0]
        assert p1_first == 0

    def test_computes_gap_between_entries(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.calculate_days_since_last()

        # p1 has entries on jan 1 and jan 3 → 2 day gap
        p1_second = result[result["patient_id"] == "p1"]["days_since_last"].iloc[1]
        assert p1_second == 2


# embedding text
class TestEmbeddingText:

    def test_includes_date_prefix(self, preprocessor, sample_df):
        preprocessor.df = sample_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.create_embedding_text()

        assert "embedding_text" in result.columns
        assert "2025-01-01" in result["embedding_text"].iloc[0]
        assert "Feeling anxious today" in result["embedding_text"].iloc[0]

    def test_omits_date_when_nat(self, preprocessor):
        # edge case: entry has no valid date — should just use content
        preprocessor.df = pd.DataFrame({
            "content": ["Test content"], "entry_date": [pd.NaT],
        })
        result = preprocessor.create_embedding_text()
        assert result["embedding_text"].iloc[0] == "Test content"


# validation
class TestValidation:

    def test_removes_duplicate_journal_ids(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "journal_id": ["j1", "j1", "j2"],
            "patient_id": ["p1", "p1", "p2"],
            "content": ["Content 1", "Content 1", "Content 2"],
        })
        preprocessor.validate()
        assert len(preprocessor.df) == 2

    def test_removes_empty_content(self, preprocessor):
        preprocessor.df = pd.DataFrame({
            "journal_id": ["j1", "j2", "j3"],
            "patient_id": ["p1", "p1", "p2"],
            "content": ["Valid content", "  ", "Another valid"],
        })
        preprocessor.validate()
        assert len(preprocessor.df) == 2

    def test_raises_on_missing_required_columns(self, preprocessor):
        # edge case: dataframe is missing journal_id and patient_id
        preprocessor.df = pd.DataFrame({"content": ["Test"]})
        with pytest.raises(ValueError, match="Missing required columns"):
            preprocessor.validate()

    def test_handles_all_empty_content(self, preprocessor):
        # edge case: every entry is whitespace
        preprocessor.df = pd.DataFrame({
            "journal_id": ["j1", "j2"],
            "patient_id": ["p1", "p1"],
            "content": ["  ", "   "],
        })
        preprocessor.validate()
        assert len(preprocessor.df) == 0


# save
class TestSave:

    def test_writes_parquet(self, preprocessor, sample_df, tmp_path):
        preprocessor.df = sample_df.copy()
        preprocessor.settings.PROCESSED_DATA_DIR = tmp_path

        path = preprocessor.save()

        assert path.exists()
        loaded = pd.read_parquet(path)
        assert len(loaded) == 3
