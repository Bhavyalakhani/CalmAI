# tests for incoming journal pipeline components
# covers: incoming journal validation, mongodb staging methods,
# patient analytics, and collection accessors

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone

import pandas as pd
import numpy as np


# incoming journal validation

class TestValidateIncomingJournals:

    @patch("validation.schema_validator.config")
    def test_valid_journals_pass(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1", "j2"],
            "patient_id": ["p1", "p1"],
            "content": ["Feeling better today after a good night sleep", "Therapy session was very helpful today"],
            "entry_date": ["2025-01-01", "2025-01-02"],
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        passed = sum(1 for r in results if r.success)
        assert passed == len(results), f"Expected all to pass, but {len(results) - passed} failed"

    @patch("validation.schema_validator.config")
    def test_empty_content_fails(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": [""],
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        failed_names = [r.name for r in results if not r.success]
        assert "string_not_empty_content" in failed_names

    @patch("validation.schema_validator.config")
    def test_too_short_content_fails(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["Hi"],  # 2 chars, under the 10 minimum
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        length_result = next(r for r in results if r.name == "content_length_bounds")
        assert not length_result.success
        assert length_result.details["too_short"] == 1

    @patch("validation.schema_validator.config")
    def test_spam_content_detected(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["aaaaaaaaaaaaaaaaaaaaaaaaaaaa"],  # repeated char spam
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        spam_result = next(r for r in results if r.name == "content_not_spam")
        assert not spam_result.success
        assert spam_result.details["spam_count"] == 1

    @patch("validation.schema_validator.config")
    def test_future_date_detected(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["A normal journal entry about my day today"],
            "entry_date": ["2099-12-31"],
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        date_result = next(r for r in results if r.name == "entry_date_not_future")
        assert not date_result.success
        assert date_result.details["future_count"] == 1

    @patch("validation.schema_validator.config")
    def test_duplicate_journal_ids_detected(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1", "j1"],
            "patient_id": ["p1", "p1"],
            "content": ["Entry one is a valid entry", "Entry two is also valid enough"],
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        unique_result = next(r for r in results if r.name == "column_unique_journal_id")
        assert not unique_result.success

    @patch("validation.schema_validator.config")
    def test_missing_patient_id_fails(self, mock_config, mock_settings):
        mock_config.settings = mock_settings
        from validation.schema_validator import SchemaValidator

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "content": ["A perfectly valid journal entry about my day"],
        })

        validator = SchemaValidator()
        results = validator.validate_incoming_journals(df)
        exists_result = next(r for r in results if r.name == "column_exists_patient_id")
        assert not exists_result.success


# mongodb staging methods

class TestMongoDBStagingMethods:

    @patch("storage.mongodb_client.MongoClient")
    def test_fetch_unprocessed_journals(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_collection.find.return_value = [
            {"journal_id": "j1", "content": "entry 1", "is_processed": False},
            {"journal_id": "j2", "content": "entry 2", "is_processed": False},
        ]
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings
        result = client.fetch_unprocessed_journals()
        assert len(result) == 2
        mock_collection.find.assert_called_once_with({"is_processed": False})

    @patch("storage.mongodb_client.MongoClient")
    def test_mark_journals_processed(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_collection.update_many.return_value = MagicMock(modified_count=3)
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings
        client.mark_journals_processed(["j1", "j2", "j3"])

        mock_collection.update_many.assert_called_once_with(
            {"journal_id": {"$in": ["j1", "j2", "j3"]}},
            {"$set": {"is_processed": True}},
        )

    @patch("storage.mongodb_client.MongoClient")
    def test_mark_empty_list_does_nothing(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings
        client.connect()
        client.mark_journals_processed([])
        mock_collection.update_many.assert_not_called()

    @patch("storage.mongodb_client.MongoClient")
    def test_insert_incoming_journals_appends(self, MockClient, mock_settings):
        """insert_incoming_journals should NOT clear existing data (append mode)"""
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_collection.insert_many.return_value = MagicMock(inserted_ids=["id1"])
        mock_collection.delete_many = MagicMock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["entry"],
            "embedding": [np.zeros(384).tolist()],
            "embedding_text": ["[2025-01-01] entry"],
            "therapist_id": ["t1"],
            "entry_date": ["2025-01-01"],
            "word_count": [1],
            "char_count": [5],
            "sentence_count": [1],
            "avg_word_length": [5.0],
            "day_of_week": [2],
            "week_number": [1],
            "month": [1],
            "year": [2025],
            "days_since_last": [0],
        })

        result = client.insert_incoming_journals(df)
        # must NOT call delete_many (append mode, not clear+replace)
        mock_collection.delete_many.assert_not_called()
        assert "rag_vectors" in result
        assert "journals" in result

    @patch("storage.mongodb_client.MongoClient")
    def test_upsert_patient_analytics(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        analytics = {"total_entries": 10, "topic_distribution": [{"topic_id": 0, "label": "anxiety", "percentage": 40}]}
        client.upsert_patient_analytics("p1", analytics)

        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"patient_id": "p1"}
        assert call_args[1].get("upsert") is True

    @patch("storage.mongodb_client.MongoClient")
    def test_collection_stats_include_new_collections(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_collection.count_documents.return_value = 5
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        stats = client.get_collection_stats()
        assert "incoming_journals" in stats
        assert "patient_analytics" in stats


# patient analytics

class TestPatientAnalytics:

    def test_classify_topics_no_model(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False
        result = pa.classify_topics("I feel so anxious and worried today")
        assert result["label"] == "unclassified"
        assert result["topic_id"] == -1

    def test_classify_topics_no_model_any_text(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False
        # without model, all text returns unclassified
        result = pa.classify_topics("I'm depressed and can't sleep at all")
        assert result["label"] == "unclassified"

    def test_classify_topics_unclassified(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False
        result = pa.classify_topics("The weather is nice")
        assert result["label"] == "unclassified"

    def test_compute_analytics_no_model(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False

        journals = [
            {"content": "Feeling anxious about tomorrow", "entry_date": "2025-01-01"},
            {"content": "Had a good therapy session today", "entry_date": "2025-01-03"},
            {"content": "Work is really stressful lately", "entry_date": "2025-02-01"},
        ]

        result = pa.compute_patient_analytics(journals)
        assert result["total_entries"] == 3
        assert result["topic_distribution"] == []
        assert result["avg_word_count"] > 0
        assert result["date_range"] is not None
        assert result["date_range"]["span_days"] > 0
        assert result["model_version"] == "unavailable"

    def test_compute_analytics_empty(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False

        result = pa.compute_patient_analytics([])
        assert result["total_entries"] == 0
        assert result["topic_distribution"] == []

    def test_entry_frequency_by_month(self):
        from analytics.patient_analytics import PatientAnalytics
        pa = PatientAnalytics()
        pa._model_loaded = False

        journals = [
            {"content": "Entry jan 1", "entry_date": "2025-01-05"},
            {"content": "Entry jan 2", "entry_date": "2025-01-15"},
            {"content": "Entry feb 1", "entry_date": "2025-02-10"},
        ]

        result = pa.compute_patient_analytics(journals)
        assert len(result["entry_frequency"]) >= 2  # at least 2 months
