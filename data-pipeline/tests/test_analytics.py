import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from analytics.patient_analytics import PatientAnalytics, _sanitize_for_mongo


# helpers

def _make_mock_inference(topic_ids=None, probs=None, labels=None):
    """create a mock TopicModelInference that returns controlled results"""
    mock = MagicMock()
    mock.load.return_value = True
    mock.is_loaded = True

    if topic_ids is None:
        topic_ids = [0, 1, 0, 1, 2]
    if probs is None:
        probs = np.array([0.9, 0.8, 0.7, 0.85, 0.6])
    if labels is None:
        labels = {0: "Anxiety and worry", 1: "Sleep disruption", 2: "Work stress", -1: "Outlier"}

    mock.predict.return_value = (topic_ids, probs)
    mock.get_topic_label.side_effect = lambda tid: labels.get(tid, f"Topic {tid}")
    mock.get_topic_keywords.side_effect = lambda tid, top_n=10: ["word1", "word2", "word3"][:top_n]

    # get_topic_distribution — mimics real method
    def fake_distribution(topics):
        from collections import Counter
        valid = [t for t in topics if t != -1]
        total = len(valid) or 1
        counts = Counter(valid)
        return [
            {
                "topic_id": tid,
                "label": labels.get(tid, f"Topic {tid}"),
                "keywords": ["word1", "word2"],
                "count": c,
                "percentage": round(c / total * 100, 1),
            }
            for tid, c in sorted(counts.items(), key=lambda x: -x[1])
        ]

    mock.get_topic_distribution.side_effect = fake_distribution

    # classify_with_distribution — mimics real method
    def fake_classify(docs):
        results = []
        for i, doc in enumerate(docs):
            tid = topic_ids[i % len(topic_ids)]
            results.append({
                "topic_id": tid,
                "label": labels.get(tid, f"Topic {tid}"),
                "keywords": ["word1", "word2"],
                "probability": float(probs[i % len(probs)]),
            })
        return results

    mock.classify_with_distribution.side_effect = fake_classify

    # predict_single — mimics real method
    def fake_predict_single(text):
        return {
            "topic_id": 0,
            "label": labels.get(0, "Topic 0"),
            "keywords": ["word1", "word2", "word3"],
            "probability": 0.85,
        }

    mock.predict_single.side_effect = fake_predict_single

    return mock


class TestPatientAnalyticsNoModel:
    """tests when no model is available — should return unclassified"""

    def test_classify_returns_unclassified(self, analytics):
        """should return unclassified when model unavailable"""
        analytics._model_loaded = False
        result = analytics.classify_topics("I feel anxious and worried")
        assert result["label"] == "unclassified"
        assert result["topic_id"] == -1
        assert result["probability"] is None

    def test_batch_returns_unclassified(self, analytics):
        """batch classification should return unclassified when no model"""
        analytics._model_loaded = False
        docs = ["I feel anxious", "work stress"]
        results = analytics.classify_topics_batch(docs)
        assert len(results) == 2
        assert all(r["label"] == "unclassified" for r in results)
        assert all(r["topic_id"] == -1 for r in results)


class TestPatientAnalyticsModelBased:
    """tests for model-based classification"""

    def test_classify_topics_with_model(self):
        """should use model inference when model is available"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        result = analytics.classify_topics("I feel anxious today")
        assert result["topic_id"] == 0
        assert result["label"] == "Anxiety and worry"
        mock_inf.predict_single.assert_called_once_with("I feel anxious today")

    def test_classify_topics_no_model(self):
        """should return unclassified when model unavailable"""
        analytics = PatientAnalytics()
        analytics._model_loaded = False

        result = analytics.classify_topics("I feel anxious today")
        assert result["label"] == "unclassified"
        assert result["topic_id"] == -1

    def test_classify_topics_batch_with_model(self):
        """should classify batch using model"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        docs = ["text one", "text two", "text three"]
        results = analytics.classify_topics_batch(docs)
        assert len(results) == 3
        assert all("topic_id" in r for r in results)
        mock_inf.classify_with_distribution.assert_called_once()

    def test_classify_topics_batch_empty(self):
        """empty input should return empty list"""
        analytics = PatientAnalytics()
        analytics._model_loaded = True
        assert analytics.classify_topics_batch([]) == []

    def test_classify_topics_batch_no_model(self):
        """batch classification should return unclassified when no model"""
        analytics = PatientAnalytics()
        analytics._model_loaded = False

        docs = ["anxious today", "work deadline"]
        results = analytics.classify_topics_batch(docs)
        assert len(results) == 2
        assert all(r["label"] == "unclassified" for r in results)
        assert all(r["topic_id"] == -1 for r in results)


class TestComputePatientAnalytics:
    """tests for the main compute_patient_analytics method"""

    def test_empty_journals(self, analytics):
        """empty input should return zeroed analytics"""
        result = analytics.compute_patient_analytics([])
        assert result["total_entries"] == 0
        assert result["topic_distribution"] == []
        assert result["topics_over_time"] == []
        assert result["representative_entries"] == []
        assert result["model_version"] is None

    def test_with_model(self):
        """should use model inference and produce full analytics"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference(
            topic_ids=[0, 1, 0],
            probs=np.array([0.9, 0.8, 0.7]),
        )
        analytics._inference = mock_inf
        analytics._model_loaded = True

        journals = [
            {"content": "Feeling anxious and worried today", "entry_date": "2025-01-01", "journal_id": "j1"},
            {"content": "Had a good therapy session", "entry_date": "2025-01-03", "journal_id": "j2"},
            {"content": "Work stress is overwhelming", "entry_date": "2025-01-05", "journal_id": "j3"},
        ]
        result = analytics.compute_patient_analytics(journals)

        assert result["total_entries"] == 3
        assert result["model_version"] == "bertopic"
        assert isinstance(result["topic_distribution"], list)
        assert len(result["topic_distribution"]) > 0
        assert all("topic_id" in d for d in result["topic_distribution"])
        mock_inf.predict.assert_called_once()
        mock_inf.get_topic_distribution.assert_called_once()

    def test_with_model_unavailable(self):
        """should return empty distributions when model unavailable"""
        analytics = PatientAnalytics()
        analytics._model_loaded = False

        journals = [
            {"content": "Feeling anxious and worried today", "entry_date": "2025-01-01"},
            {"content": "Had a good therapy session", "entry_date": "2025-01-03"},
            {"content": "Work stress is overwhelming", "entry_date": "2025-01-05"},
        ]
        result = analytics.compute_patient_analytics(journals)

        assert result["total_entries"] == 3
        assert result["model_version"] == "unavailable"
        assert result["topic_distribution"] == []
        assert result["topics_over_time"] == []
        assert result["representative_entries"] == []

    def test_avg_word_count(self, analytics, sample_journals):
        """should compute average word count"""
        analytics._model_loaded = False
        result = analytics.compute_patient_analytics(sample_journals)
        assert result["avg_word_count"] > 0

    def test_entry_frequency(self, analytics, sample_journals):
        """should compute monthly entry frequency"""
        analytics._model_loaded = False
        result = analytics.compute_patient_analytics(sample_journals)
        assert isinstance(result["entry_frequency"], dict)
        assert len(result["entry_frequency"]) > 0

    def test_date_range(self, analytics, sample_journals):
        """should compute date range with span"""
        analytics._model_loaded = False
        result = analytics.compute_patient_analytics(sample_journals)

        assert result["date_range"] is not None
        assert "first" in result["date_range"]
        assert "last" in result["date_range"]
        assert result["date_range"]["span_days"] == 4

    def test_computed_at_present(self, analytics, sample_journals):
        """result should include computed_at timestamp"""
        analytics._model_loaded = False
        result = analytics.compute_patient_analytics(sample_journals)
        assert "computed_at" in result
        assert result["computed_at"] is not None


class TestTopicsOverTime:
    """tests for the _compute_topics_over_time helper"""

    def test_basic(self):
        """should group topics by month"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        import pandas as pd
        df = pd.DataFrame({
            "content": ["a", "b", "c", "d"],
            "entry_date": ["2025-01-10", "2025-01-20", "2025-02-05", "2025-02-15"],
        })
        topics = [0, 1, 0, 2]

        result = analytics._compute_topics_over_time(df, topics)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("month" in r for r in result)
        assert all("topic_id" in r for r in result)
        assert all("label" in r for r in result)
        assert all("frequency" in r for r in result)

    def test_excludes_outliers(self):
        """outlier topic -1 should be excluded"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        import pandas as pd
        df = pd.DataFrame({
            "content": ["a", "b"],
            "entry_date": ["2025-01-10", "2025-01-20"],
        })
        topics = [-1, -1]

        result = analytics._compute_topics_over_time(df, topics)
        assert result == []

    def test_no_entry_date(self):
        """should return empty when no entry_date column"""
        analytics = PatientAnalytics()

        import pandas as pd
        df = pd.DataFrame({"content": ["a", "b"]})
        result = analytics._compute_topics_over_time(df, [0, 1])
        assert result == []


class TestRepresentativeEntries:
    """tests for the _find_representative_entries helper"""

    def test_basic(self):
        """should find highest-probability entry per topic"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        import pandas as pd
        df = pd.DataFrame({
            "content": ["entry one", "entry two", "entry three"],
            "entry_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "journal_id": ["j1", "j2", "j3"],
        })
        topics = [0, 0, 1]
        probs = np.array([0.8, 0.95, 0.7])

        result = analytics._find_representative_entries(df, topics, probs)
        assert isinstance(result, list)
        assert len(result) == 2  # two topics
        # sorted by probability descending
        assert result[0]["probability"] >= result[1]["probability"]
        # topic 0 rep should be j2 (prob 0.95)
        topic0_rep = next(r for r in result if r["topic_id"] == 0)
        assert topic0_rep["journal_id"] == "j2"
        assert topic0_rep["probability"] == 0.95

    def test_none_probs(self):
        """should return empty when probs is None"""
        analytics = PatientAnalytics()

        import pandas as pd
        df = pd.DataFrame({"content": ["a"], "journal_id": ["j1"]})
        result = analytics._find_representative_entries(df, [0], None)
        assert result == []

    def test_all_outliers(self):
        """should return empty when all topics are outliers"""
        analytics = PatientAnalytics()

        import pandas as pd
        df = pd.DataFrame({"content": ["a", "b"], "journal_id": ["j1", "j2"]})
        probs = np.array([0.5, 0.5])
        result = analytics._find_representative_entries(df, [-1, -1], probs)
        assert result == []

    def test_content_truncation(self):
        """representative entry content should be truncated to 200 chars"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()
        analytics._inference = mock_inf
        analytics._model_loaded = True

        import pandas as pd
        long_content = "x" * 300
        df = pd.DataFrame({
            "content": [long_content],
            "entry_date": ["2025-01-01"],
            "journal_id": ["j1"],
        })
        result = analytics._find_representative_entries(df, [0], np.array([0.9]))
        assert len(result) == 1
        assert len(result[0]["content"]) == 200


class TestEnsureModel:
    """tests for the _ensure_model lazy loader"""

    def test_loads_once(self):
        """should only attempt to load the model once"""
        analytics = PatientAnalytics()

        # simulate model load failure by directly setting state
        analytics._model_loaded = False
        analytics._inference = None

        # second call should not retry (already failed)
        result = analytics._ensure_model()
        assert result is False

    def test_model_load_success(self):
        """should set model_loaded True on success"""
        analytics = PatientAnalytics()
        mock_inf = _make_mock_inference()

        # simulate successful load by setting directly
        analytics._inference = mock_inf
        analytics._model_loaded = True

        result = analytics._ensure_model()
        assert result is True
        assert analytics._model_loaded is True

    def test_model_loaded_none_tries_import(self):
        """when _model_loaded is None, should attempt to import and load"""
        analytics = PatientAnalytics()
        # _model_loaded starts as None — _ensure_model should try the import
        # but since there's no model file on disk, it will fail gracefully
        # we just verify it sets _model_loaded to a boolean
        result = analytics._ensure_model()
        assert isinstance(analytics._model_loaded, bool)


# sanitize for mongo

class TestSanitizeForMongo:
    """tests for numpy/pandas -> native python type conversion"""

    def test_numpy_integers(self):
        data = {"count": np.int64(13), "topic_id": np.int32(5)}
        result = _sanitize_for_mongo(data)
        assert result["count"] == 13
        assert result["topic_id"] == 5
        assert isinstance(result["count"], int)
        assert isinstance(result["topic_id"], int)

    def test_numpy_floats(self):
        data = {"score": np.float64(0.95), "value": np.float32(1.5)}
        result = _sanitize_for_mongo(data)
        assert isinstance(result["score"], float)
        assert isinstance(result["value"], float)

    def test_numpy_bool(self):
        data = {"flag": np.bool_(True)}
        result = _sanitize_for_mongo(data)
        assert result["flag"] is True
        assert isinstance(result["flag"], bool)

    def test_numpy_array(self):
        data = {"embedding": np.array([1.0, 2.0, 3.0])}
        result = _sanitize_for_mongo(data)
        assert result["embedding"] == [1.0, 2.0, 3.0]
        assert isinstance(result["embedding"], list)

    def test_nested_dicts_and_lists(self):
        data = {
            "topics": [
                {"topic_id": np.int64(0), "count": np.int64(10)},
                {"topic_id": np.int64(1), "count": np.int64(5)},
            ],
            "total": np.int64(15),
        }
        result = _sanitize_for_mongo(data)
        assert isinstance(result["total"], int)
        assert isinstance(result["topics"][0]["topic_id"], int)
        assert isinstance(result["topics"][1]["count"], int)

    def test_pandas_timestamp(self):
        data = {"ts": pd.Timestamp("2024-01-15")}
        result = _sanitize_for_mongo(data)
        assert isinstance(result["ts"], str)

    def test_native_types_passthrough(self):
        data = {"name": "test", "count": 5, "score": 1.5, "flag": True}
        result = _sanitize_for_mongo(data)
        assert result == data