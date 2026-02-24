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
    def test_insert_incoming_journals_upserts(self, MockClient, mock_settings):
        """insert_incoming_journals should upsert journals and clean+insert rag_vectors"""
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_journals_col = MagicMock()
        mock_rag_col = MagicMock()
        mock_rag_col.insert_many.return_value = MagicMock(inserted_ids=["id1"])

        def get_collection(name):
            if name == "journals":
                return mock_journals_col
            elif name == "rag_vectors":
                return mock_rag_col
            return MagicMock()

        mock_db.__getitem__ = Mock(side_effect=get_collection)

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
        # journals should use upsert (update_one), not insert_many
        mock_journals_col.update_one.assert_called_once()
        call_args = mock_journals_col.update_one.call_args
        assert call_args[0][0] == {"journal_id": "j1"}
        assert call_args[1].get("upsert") is True

        # rag_vectors should delete old entries then batch insert new ones
        mock_rag_col.delete_many.assert_called_once()
        mock_rag_col.insert_many.assert_called_once()

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


# prompt_id and mood passthrough

class TestPromptMoodPassthrough:

    @patch("storage.mongodb_client.MongoClient")
    def test_insert_incoming_journals_preserves_prompt_id_and_mood(self, MockClient, mock_settings):
        """prompt_id and mood should pass through to both journals and rag_vectors"""
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        # capture rag_vectors inserts
        rag_inserted = []
        mock_rag_col = MagicMock()
        def capture_rag_insert(docs, **kwargs):
            rag_inserted.extend(docs)
            return MagicMock(inserted_ids=[f"id{i}" for i in range(len(docs))])
        mock_rag_col.insert_many.side_effect = capture_rag_insert
        mock_rag_col.delete_many = MagicMock()

        # capture journals upserts
        journal_upserts = []
        mock_journals_col = MagicMock()
        def capture_upsert(filter_doc, update_doc, **kwargs):
            journal_upserts.append({"filter": filter_doc, "update": update_doc, **kwargs})
            return MagicMock(upserted_id="id1")
        mock_journals_col.update_one.side_effect = capture_upsert

        def get_collection(name):
            if name == "rag_vectors":
                return mock_rag_col
            elif name == "journals":
                return mock_journals_col
            return MagicMock()

        mock_db.__getitem__ = Mock(side_effect=get_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["responded to therapist prompt"],
            "embedding": [np.zeros(384).tolist()],
            "embedding_text": ["[2025-01-01] responded to therapist prompt"],
            "therapist_id": ["t1"],
            "entry_date": ["2025-01-01"],
            "word_count": [5],
            "char_count": [30],
            "sentence_count": [1],
            "avg_word_length": [6.0],
            "day_of_week": [2],
            "week_number": [1],
            "month": [1],
            "year": [2025],
            "days_since_last": [0],
            "prompt_id": ["pr-001"],
            "mood": [4],
        })

        result = client.insert_incoming_journals(df)

        # check journals upsert has prompt_id and mood
        assert len(journal_upserts) == 1
        journal_set = journal_upserts[0]["update"]["$set"]
        assert journal_set["prompt_id"] == "pr-001"
        assert journal_set["mood"] == 4

        # check vector doc metadata has prompt_id and mood
        assert len(rag_inserted) == 1
        vec_doc = rag_inserted[0]
        assert vec_doc["metadata"]["prompt_id"] == "pr-001"
        assert vec_doc["metadata"]["mood"] == 4

    @patch("storage.mongodb_client.MongoClient")
    def test_insert_incoming_journals_handles_missing_prompt_id_and_mood(self, MockClient, mock_settings):
        """when prompt_id and mood are absent, they should be None (not raise)"""
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_rag_col = MagicMock()
        mock_rag_col.insert_many.return_value = MagicMock(inserted_ids=["id1"])
        mock_rag_col.delete_many = MagicMock()
        mock_journals_col = MagicMock()

        def get_collection(name):
            if name == "rag_vectors":
                return mock_rag_col
            elif name == "journals":
                return mock_journals_col
            return MagicMock()

        mock_db.__getitem__ = Mock(side_effect=get_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        df = pd.DataFrame({
            "journal_id": ["j1"],
            "patient_id": ["p1"],
            "content": ["regular entry no prompt"],
            "embedding": [np.zeros(384).tolist()],
            "embedding_text": ["[2025-01-01] regular entry no prompt"],
            "therapist_id": ["t1"],
            "entry_date": ["2025-01-01"],
            "word_count": [4],
            "char_count": [24],
            "sentence_count": [1],
            "avg_word_length": [6.0],
            "day_of_week": [2],
            "week_number": [1],
            "month": [1],
            "year": [2025],
            "days_since_last": [0],
        })

        # should not raise
        result = client.insert_incoming_journals(df)
        assert "rag_vectors" in result
        assert "journals" in result


# conditional retrain

def _get_xcom_pushes(mock_ti):
    """extract xcom_push calls into a key->value dict, handling False/None correctly"""
    push_calls = {}
    for call in mock_ti.xcom_push.call_args_list:
        args, kwargs = call
        key = kwargs.get("key") if "key" in kwargs else (args[0] if args else None)
        value = kwargs["value"] if "value" in kwargs else (args[1] if len(args) > 1 else None)
        if key:
            push_calls[key] = value
    return push_calls


class TestConditionalRetrain:

    @staticmethod
    def _import_callable():
        """import conditional_retrain_callable with airflow mocked out"""
        import sys
        from unittest.mock import MagicMock

        # mock airflow modules so the dag file can be imported without airflow installed
        airflow_mock = MagicMock()
        modules_to_mock = {
            "airflow": airflow_mock,
            "airflow.operators": airflow_mock.operators,
            "airflow.operators.python": airflow_mock.operators.python,
            "airflow.operators.empty": airflow_mock.operators.empty,
        }
        saved = {}
        for mod_name, mod_mock in modules_to_mock.items():
            saved[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mod_mock

        # make DAG a context manager mock
        airflow_mock.DAG.return_value.__enter__ = MagicMock(return_value=MagicMock())
        airflow_mock.DAG.return_value.__exit__ = MagicMock(return_value=False)

        try:
            # force reimport
            if "dags.incoming_journals_pipeline" in sys.modules:
                del sys.modules["dags.incoming_journals_pipeline"]
            from dags.incoming_journals_pipeline import conditional_retrain_callable
            return conditional_retrain_callable
        finally:
            # restore airflow modules but keep dags module cached for patch() to work
            for mod_name, original in saved.items():
                if original is None:
                    sys.modules.pop(mod_name, None)
                else:
                    sys.modules[mod_name] = original

    @patch("storage.mongodb_client.MongoClient")
    def test_get_last_training_metadata_returns_none_when_empty(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        result = client.get_last_training_metadata()
        assert result is None
        mock_collection.find_one.assert_called_once()

    @patch("storage.mongodb_client.MongoClient")
    def test_get_last_training_metadata_returns_doc(self, MockClient, mock_settings):
        from storage.mongodb_client import MongoDBClient
        from bson import ObjectId

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client.admin.command.return_value = True

        doc = {
            "_id": ObjectId(),
            "type": "training_metadata",
            "journal_count": 100,
            "conversation_count": 3500,
            "trained_at": "2025-01-01T00:00:00+00:00",
            "reason": "baseline",
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = doc
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        client = MongoDBClient(uri="mongodb://test", database="test_db")
        client.settings = mock_settings

        result = client.get_last_training_metadata()
        assert result is not None
        assert result["journal_count"] == 100
        assert isinstance(result["_id"], str)

    @patch("storage.mongodb_client.MongoClient")
    def test_save_training_metadata(self, MockClient, mock_settings):
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

        metadata = {
            "journal_count": 150,
            "conversation_count": 3500,
            "trained_at": "2025-06-01T00:00:00+00:00",
            "reason": "50 new entries",
        }
        client.save_training_metadata(metadata)
        mock_collection.insert_one.assert_called_once()
        inserted = mock_collection.insert_one.call_args[0][0]
        assert inserted["type"] == "training_metadata"
        assert inserted["journal_count"] == 150

    def test_retrain_callable_skips_when_no_metadata(self, mock_settings):
        """first run saves baseline metadata without training"""
        conditional_retrain_callable = self._import_callable()

        mock_ti = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.journals.count_documents.return_value = 100
        mock_client_instance.conversations.count_documents.return_value = 3500
        mock_client_instance.get_last_training_metadata.return_value = None

        with patch("storage.mongodb_client.MongoDBClient", return_value=mock_client_instance):
            with patch("config.settings", mock_settings):
                mock_settings.RETRAIN_ENTRY_THRESHOLD = 50
                mock_settings.RETRAIN_MAX_DAYS = 7
                conditional_retrain_callable(ti=mock_ti)

        # should save baseline metadata
        mock_client_instance.save_training_metadata.assert_called_once()
        saved = mock_client_instance.save_training_metadata.call_args[0][0]
        assert saved["reason"] == "baseline"
        assert saved["journal_count"] == 100

        push_calls = _get_xcom_pushes(mock_ti)
        assert push_calls.get("retrain_triggered") is False

    def test_retrain_callable_skips_when_thresholds_not_met(self, mock_settings):
        """does not retrain when below both thresholds"""
        conditional_retrain_callable = self._import_callable()

        mock_ti = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.journals.count_documents.return_value = 120
        mock_client_instance.conversations.count_documents.return_value = 3500
        mock_client_instance.get_last_training_metadata.return_value = {
            "_id": "abc",
            "type": "training_metadata",
            "journal_count": 100,
            "conversation_count": 3500,
            "trained_at": datetime.now(timezone.utc).isoformat(),  # just trained
            "reason": "baseline",
        }

        with patch("storage.mongodb_client.MongoDBClient", return_value=mock_client_instance):
            with patch("config.settings", mock_settings):
                mock_settings.RETRAIN_ENTRY_THRESHOLD = 50
                mock_settings.RETRAIN_MAX_DAYS = 7
                conditional_retrain_callable(ti=mock_ti)

        # should not save new metadata or retrain
        mock_client_instance.save_training_metadata.assert_not_called()

        push_calls = _get_xcom_pushes(mock_ti)
        assert push_calls.get("retrain_triggered") is False
        assert "thresholds not met" in push_calls.get("retrain_reason", "")

    def test_retrain_callable_triggers_on_entry_threshold(self, mock_settings):
        """triggers retrain when entry threshold is met"""
        conditional_retrain_callable = self._import_callable()

        mock_ti = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.journals.count_documents.return_value = 200
        mock_client_instance.conversations.count_documents.return_value = 3500
        mock_client_instance.get_last_training_metadata.return_value = {
            "_id": "abc",
            "type": "training_metadata",
            "journal_count": 100,  # 100 new entries > 50 threshold
            "conversation_count": 3500,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "reason": "baseline",
        }
        mock_client_instance.journals.find.return_value = [
            {"journal_id": f"j{i}", "patient_id": "p1", "content": f"Journal entry {i}", "entry_date": "2025-01-01"}
            for i in range(200)
        ]
        mock_client_instance.conversations.find.return_value = [
            {"conversation_id": f"c{i}", "context": f"Context {i}", "response": f"Response {i}"}
            for i in range(100)
        ]

        mock_trainer_instance = MagicMock()
        mock_trainer_instance.prepare_journal_docs.return_value = (["doc"] * 200, ["2025-01-01"] * 200)
        mock_trainer_instance.prepare_conversation_docs.return_value = (["doc"] * 100, None)
        mock_trainer_instance.train.return_value = {
            "num_topics": 5, "num_documents": 200, "outlier_ratio": 0.1,
            "model_type": "journals", "training_duration_seconds": 10,
        }
        mock_trainer_instance.save_model.return_value = "/tmp/model"
        mock_trainer_instance.topics = [0] * 200
        mock_trainer_instance.model = MagicMock()

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_all.return_value = {"overall_pass": True}

        with patch("storage.mongodb_client.MongoDBClient", return_value=mock_client_instance):
            with patch("config.settings", mock_settings):
                mock_settings.RETRAIN_ENTRY_THRESHOLD = 50
                mock_settings.RETRAIN_MAX_DAYS = 7
                with patch("topic_modeling.trainer.TopicModelTrainer", return_value=mock_trainer_instance):
                    with patch("topic_modeling.validation.TopicModelValidator", return_value=mock_validator_instance):
                        conditional_retrain_callable(ti=mock_ti)

        # should save training metadata
        mock_client_instance.save_training_metadata.assert_called_once()
        saved = mock_client_instance.save_training_metadata.call_args[0][0]
        assert saved["journal_count"] == 200
        assert "results" in saved

        push_calls = _get_xcom_pushes(mock_ti)
        assert push_calls.get("retrain_triggered") is True

    def test_retrain_callable_triggers_on_time_threshold(self, mock_settings):
        """triggers retrain when time threshold is met"""
        conditional_retrain_callable = self._import_callable()
        from datetime import timedelta

        mock_ti = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.journals.count_documents.return_value = 105
        mock_client_instance.conversations.count_documents.return_value = 3500
        # trained 10 days ago, only 5 new entries (below entry threshold)
        trained_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        mock_client_instance.get_last_training_metadata.return_value = {
            "_id": "abc",
            "type": "training_metadata",
            "journal_count": 100,
            "conversation_count": 3500,
            "trained_at": trained_at,
            "reason": "baseline",
        }
        mock_client_instance.journals.find.return_value = [
            {"journal_id": f"j{i}", "patient_id": "p1", "content": f"Journal entry {i}", "entry_date": "2025-01-01"}
            for i in range(105)
        ]
        mock_client_instance.conversations.find.return_value = [
            {"conversation_id": f"c{i}", "context": f"Context {i}", "response": f"Response {i}"}
            for i in range(100)
        ]

        mock_trainer_instance = MagicMock()
        mock_trainer_instance.prepare_journal_docs.return_value = (["doc"] * 105, ["2025-01-01"] * 105)
        mock_trainer_instance.prepare_conversation_docs.return_value = (["doc"] * 100, None)
        mock_trainer_instance.train.return_value = {
            "num_topics": 5, "num_documents": 105, "outlier_ratio": 0.1,
            "model_type": "journals", "training_duration_seconds": 10,
        }
        mock_trainer_instance.save_model.return_value = "/tmp/model"
        mock_trainer_instance.topics = [0] * 105
        mock_trainer_instance.model = MagicMock()

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_all.return_value = {"overall_pass": True}

        with patch("storage.mongodb_client.MongoDBClient", return_value=mock_client_instance):
            with patch("config.settings", mock_settings):
                mock_settings.RETRAIN_ENTRY_THRESHOLD = 50
                mock_settings.RETRAIN_MAX_DAYS = 7
                with patch("topic_modeling.trainer.TopicModelTrainer", return_value=mock_trainer_instance):
                    with patch("topic_modeling.validation.TopicModelValidator", return_value=mock_validator_instance):
                        conditional_retrain_callable(ti=mock_ti)

        push_calls = _get_xcom_pushes(mock_ti)
        assert push_calls.get("retrain_triggered") is True
        assert "days since last training" in push_calls.get("retrain_reason", "")

    def test_retrain_callable_skips_small_corpus(self, mock_settings):
        """skips model training when corpus is too small (<20 docs)"""
        conditional_retrain_callable = self._import_callable()

        mock_ti = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.journals.count_documents.return_value = 60
        mock_client_instance.conversations.count_documents.return_value = 10
        mock_client_instance.get_last_training_metadata.return_value = {
            "_id": "abc",
            "type": "training_metadata",
            "journal_count": 5,  # 55 new > 50 threshold
            "conversation_count": 10,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "reason": "baseline",
        }
        # 60 journals but only 10 conversations
        mock_client_instance.journals.find.return_value = [
            {"journal_id": f"j{i}", "patient_id": "p1", "content": f"Journal entry {i}", "entry_date": "2025-01-01"}
            for i in range(60)
        ]
        mock_client_instance.conversations.find.return_value = [
            {"conversation_id": f"c{i}", "context": f"Context {i}", "response": f"Response {i}"}
            for i in range(10)
        ]

        mock_trainer_instance = MagicMock()
        mock_trainer_instance.prepare_journal_docs.return_value = (["doc"] * 60, ["2025-01-01"] * 60)
        mock_trainer_instance.train.return_value = {
            "num_topics": 3, "num_documents": 60, "outlier_ratio": 0.05,
            "model_type": "journals", "training_duration_seconds": 5,
        }
        mock_trainer_instance.save_model.return_value = "/tmp/model"
        mock_trainer_instance.topics = [0] * 60
        mock_trainer_instance.model = MagicMock()

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_all.return_value = {"overall_pass": True}

        with patch("storage.mongodb_client.MongoDBClient", return_value=mock_client_instance):
            with patch("config.settings", mock_settings):
                mock_settings.RETRAIN_ENTRY_THRESHOLD = 50
                mock_settings.RETRAIN_MAX_DAYS = 7
                with patch("topic_modeling.trainer.TopicModelTrainer", return_value=mock_trainer_instance):
                    with patch("topic_modeling.validation.TopicModelValidator", return_value=mock_validator_instance):
                        conditional_retrain_callable(ti=mock_ti)

        # journal model trained (60 >= 20), conversation + severity skipped (10 < 20)
        mock_client_instance.save_training_metadata.assert_called_once()
        saved = mock_client_instance.save_training_metadata.call_args[0][0]
        results = saved.get("results", {})
        assert "journals" in results
        # conversation and severity should not be in results (skipped due to small corpus)
        assert "conversations" not in results
        assert "severity" not in results
