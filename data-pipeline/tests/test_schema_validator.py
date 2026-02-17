# tests for schema_validator.py
# covers all expectation primitives (exists, unique, not-null, range, type, string-not-empty),
# full conversation + journal validation, report generation, and saving

import pytest
from unittest.mock import Mock
from pathlib import Path
import pandas as pd
import numpy as np

from validation.schema_validator import SchemaValidator, ExpectationResult, ValidationReport


@pytest.fixture
def validator(mock_settings):
    val = SchemaValidator()
    val.settings = mock_settings
    return val


# expectation primitives
class TestExpectColumnExists:

    def test_passes_when_column_present(self, validator, conversations_processed_df):
        result = validator.expect_column_exists(conversations_processed_df, "context")
        assert result.success is True

    def test_fails_when_column_missing(self, validator, conversations_processed_df):
        result = validator.expect_column_exists(conversations_processed_df, "nonexistent")
        assert result.success is False


class TestExpectColumnUnique:

    def test_passes_on_unique_values(self, validator, conversations_processed_df):
        result = validator.expect_column_unique(conversations_processed_df, "conversation_id")
        assert result.success is True
        assert result.details["duplicates"] == 0

    def test_fails_on_duplicates(self, validator):
        df = pd.DataFrame({"id": ["a", "b", "a"]})
        result = validator.expect_column_unique(df, "id")
        assert result.success is False
        assert result.details["duplicates"] == 1

    def test_fails_on_missing_column(self, validator, conversations_processed_df):
        result = validator.expect_column_unique(conversations_processed_df, "nope")
        assert result.success is False
        assert "error" in result.details


class TestExpectColumnNotNull:

    def test_passes_when_no_nulls(self, validator, conversations_processed_df):
        result = validator.expect_column_not_null(conversations_processed_df, "context")
        assert result.success is True
        assert result.details["null_count"] == 0

    def test_fails_when_nulls_found(self, validator):
        df = pd.DataFrame({"col": ["a", None, "c"]})
        result = validator.expect_column_not_null(df, "col")
        assert result.success is False
        assert result.details["null_count"] == 1

    def test_detects_all_null_column(self, validator):
        # edge case: entire column is null
        df = pd.DataFrame({"col": [None, None, None]})
        result = validator.expect_column_not_null(df, "col")
        assert result.success is False
        assert result.details["null_count"] == 3


class TestExpectValueRange:

    def test_passes_within_range(self, validator, conversations_processed_df):
        result = validator.expect_value_range(conversations_processed_df, "context_word_count", min_val=3, max_val=100)
        assert result.success is True

    def test_fails_below_min(self, validator):
        df = pd.DataFrame({"score": [1, 5, 10]})
        result = validator.expect_value_range(df, "score", min_val=3)
        assert result.success is False
        assert result.details["violations"] == 1

    def test_fails_above_max(self, validator):
        df = pd.DataFrame({"score": [5, 10, 150]})
        result = validator.expect_value_range(df, "score", max_val=100)
        assert result.success is False

    def test_handles_negative_values(self, validator):
        # edge case: negative numbers in a column supposed to be positive
        df = pd.DataFrame({"count": [-1, 0, 5]})
        result = validator.expect_value_range(df, "count", min_val=0)
        assert result.success is False
        assert result.details["violations"] == 1


class TestExpectColumnType:

    def test_passes_on_correct_type(self, validator, conversations_processed_df):
        result = validator.expect_column_type(conversations_processed_df, "context_word_count", "int")
        assert result.success is True

    def test_fails_on_wrong_type(self, validator, conversations_processed_df):
        result = validator.expect_column_type(conversations_processed_df, "context", "int")
        assert result.success is False

    def test_fails_on_missing_column(self, validator, conversations_processed_df):
        result = validator.expect_column_type(conversations_processed_df, "nope", "int")
        assert result.success is False


class TestExpectStringNotEmpty:

    def test_passes_on_non_empty_strings(self, validator, conversations_processed_df):
        result = validator.expect_string_not_empty(conversations_processed_df, "context")
        assert result.success is True

    def test_fails_on_whitespace_only(self, validator):
        df = pd.DataFrame({"text": ["hello", "  ", "world", ""]})
        result = validator.expect_string_not_empty(df, "text")
        assert result.success is False
        assert result.details["empty_count"] == 2

    def test_fails_on_missing_column(self, validator, conversations_processed_df):
        result = validator.expect_string_not_empty(conversations_processed_df, "nope")
        assert result.success is False


# text statistics
class TestTextStatistics:

    def test_computes_length_and_word_stats(self, validator, conversations_processed_df):
        stats = validator.compute_text_statistics(conversations_processed_df, "context")
        assert "context_length_min" in stats
        assert "context_length_max" in stats
        assert "context_words_mean" in stats
        assert stats["context_length_min"] > 0

    def test_computes_vocabulary_richness(self, validator):
        df = pd.DataFrame({"text": ["hello world", "world hello", "test world"]})
        stats = validator.compute_vocabulary_stats(df, "text")
        assert stats["text_total_words"] == 6
        assert stats["text_unique_words"] == 3
        assert 0 < stats["text_vocab_richness"] < 1


# full validators
class TestValidateConversations:

    def test_all_pass_on_valid_data(self, validator, conversations_processed_df):
        results = validator.validate_conversations(conversations_processed_df)
        assert len(results) > 0
        assert all(r.success for r in results)

    def test_detects_missing_columns(self, validator):
        # edge case: dataframe is missing most required columns
        df = pd.DataFrame({"conversation_id": ["c1"], "context": ["Q"]})
        results = validator.validate_conversations(df)
        failed = [r for r in results if not r.success]
        assert len(failed) > 0


class TestValidateJournals:

    def test_all_pass_on_valid_data(self, validator, journals_processed_df):
        results = validator.validate_journals(journals_processed_df)
        assert len(results) > 0
        assert all(r.success for r in results)

    def test_detects_duplicate_ids(self, validator):
        df = pd.DataFrame({
            "journal_id": ["j1", "j1", "j2"],
            "patient_id": ["p1", "p1", "p2"],
            "therapist_id": ["t1", "t1", "t1"],
            "entry_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "content": ["Entry 1", "Entry 2", "Entry 3"],
            "word_count": [15, 20, 18],
        })
        results = validator.validate_journals(df)
        failed = [r for r in results if not r.success and "unique" in r.name]
        assert len(failed) > 0


# report generation
class TestReport:

    def test_report_has_pass_rate(self, validator, conversations_processed_df):
        results = validator.validate_conversations(conversations_processed_df)
        report = validator.generate_report("test", conversations_processed_df, results, ["context"])

        assert hasattr(report, "pass_rate")
        assert report.pass_rate == 100.0

    def test_report_fields_populated(self, validator, conversations_processed_df):
        results = validator.validate_conversations(conversations_processed_df)
        report = validator.generate_report("test", conversations_processed_df, results, ["context"])

        assert isinstance(report, ValidationReport)
        assert report.dataset_name == "test"
        assert report.total_records == 3
        assert report.passed > 0
        assert "record_count" in report.statistics

    def test_save_creates_json_file(self, validator, tmp_path):
        validator.settings.REPORTS_DIR = tmp_path
        report = ValidationReport(
            dataset_name="test",
            timestamp="2025-01-01T00:00:00",
            total_records=10,
            passed=8,
            failed=2,
            pass_rate=80.0,
            expectations=[],
            statistics={},
        )
        path = validator.save_report(report, "test_report.json")
        assert path.exists()
        assert path.name == "test_report.json"
