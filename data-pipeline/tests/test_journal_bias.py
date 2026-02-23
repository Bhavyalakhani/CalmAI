# tests for journal_bias.py
# covers patient distribution, sparse patients, temporal patterns,
# topic classification (model-based), topic distribution,
# outlier analysis, patient topic coverage, mitigation notes, report, viz

import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np

from bias_detection.journal_bias import JournalBiasAnalyzer, JournalBiasReport


def _make_mock_inference(topics=None, probs=None, labels=None):
    """helper — creates a mock TopicModelInference with realistic behavior"""
    mock = MagicMock()
    mock.load.return_value = True
    mock.is_loaded = True

    _labels = labels or {0: "anxiety", 1: "depression", 2: "therapy", 3: "work", -1: "Outlier"}
    _topics = topics or [0, 1, -1, 2, 3]
    _probs = probs if probs is not None else np.array([0.85, 0.72, 0.1, 0.91, 0.65])

    mock.predict.return_value = (_topics, _probs)
    mock.get_topic_label.side_effect = lambda tid: _labels.get(tid, f"Topic {tid}")
    mock.get_topic_keywords.return_value = ["feel", "anxious", "worried"]
    mock.get_all_topic_info.return_value = [
        {"topic_id": 0, "count": 20, "label": "anxiety", "keywords": ["anxious", "worried"]},
        {"topic_id": 1, "count": 15, "label": "depression", "keywords": ["depressed", "sad"]},
        {"topic_id": 2, "count": 10, "label": "therapy", "keywords": ["therapy", "session"]},
        {"topic_id": 3, "count": 8, "label": "work", "keywords": ["work", "deadline"]},
    ]

    return mock


@pytest.fixture
def analyzer(mock_settings):
    a = JournalBiasAnalyzer()
    a.settings = mock_settings
    # use mock model for tests
    mock_inf = _make_mock_inference()
    a._inference = mock_inf
    a._model_loaded = True
    a._model_version = "bertopic"
    return a


@pytest.fixture
def analyzer_with_data(analyzer, journals_df):
    """analyzer that already has data loaded and classified"""
    analyzer.df = journals_df.copy()
    from bias_detection.slicer import DataSlicer
    analyzer.slicer = DataSlicer(analyzer.df)
    analyzer.classify_topics()
    return analyzer


# patient distribution
class TestPatientDistribution:

    def test_total_patients_is_correct(self, analyzer_with_data):
        # journals_df has p1, p2, p3 → 3 patients
        dist = analyzer_with_data.analyze_patient_distribution()
        assert dist["total_patients"] == 3

    def test_entries_per_patient_stats(self, analyzer_with_data):
        dist = analyzer_with_data.analyze_patient_distribution()
        assert "entries_per_patient_mean" in dist
        assert "entries_per_patient_min" in dist
        assert "entries_per_patient_max" in dist
        # p1 has 2, p2 has 2, p3 has 1
        assert dist["entries_per_patient_min"] == 1
        assert dist["entries_per_patient_max"] == 2


# sparse patients
class TestSparsePatients:

    def test_finds_patients_below_threshold(self, analyzer_with_data):
        # default threshold is 10, all patients have < 10 entries
        sparse = analyzer_with_data.find_sparse_patients()
        assert len(sparse) == 3
        ids = {s["patient_id"] for s in sparse}
        assert "p1" in ids and "p2" in ids and "p3" in ids

    def test_no_sparse_when_all_above_threshold(self, analyzer):
        # edge case: plenty of entries per patient
        rows = [{"journal_id": f"j{i}", "patient_id": "p1", "content": f"entry {i}"} for i in range(15)]
        analyzer.df = pd.DataFrame(rows)
        sparse = analyzer.find_sparse_patients()
        assert len(sparse) == 0


# temporal patterns
class TestTemporalPatterns:

    def test_includes_by_day_and_month(self, analyzer_with_data):
        patterns = analyzer_with_data.analyze_temporal_patterns()
        assert "entries_by_day" in patterns
        assert "entries_by_month" in patterns

    def test_gap_stats_computed_when_available(self, analyzer):
        analyzer.df = pd.DataFrame({
            "day_of_week": [0, 1],
            "month": [1, 1],
            "days_since_last": [0, 5],
        })
        patterns = analyzer.analyze_temporal_patterns()
        assert "entry_gap_mean" in patterns
        assert patterns["entry_gap_mean"] == 5.0


# topic classification
class TestClassifyTopics:

    def test_creates_topic_columns(self, analyzer_with_data):
        assert "topic_id" in analyzer_with_data.df.columns
        assert "topic_label" in analyzer_with_data.df.columns
        assert "topic_probability" in analyzer_with_data.df.columns

    def test_anxiety_detected_by_model(self, analyzer_with_data):
        # row 0: classified by mock model
        row0 = analyzer_with_data.df.iloc[0]
        assert row0["topic_label"] == "anxiety"

    def test_depression_detected_by_model(self, analyzer_with_data):
        # row 1: classified by mock model
        row1 = analyzer_with_data.df.iloc[1]
        assert row1["topic_label"] == "depression"

    def test_outlier_entry_detected(self, analyzer_with_data):
        """entries with topic_id -1 get unclassified label"""
        # row 2 gets topic_id -1 from mock
        row2 = analyzer_with_data.df.iloc[2]
        assert row2["topic_id"] == -1
        assert row2["topic_label"] == "Outlier"

    def test_raises_when_no_model(self, analyzer):
        """should raise RuntimeError when model is not available"""
        analyzer._model_loaded = False
        analyzer._inference = None
        analyzer.df = pd.DataFrame({"content": ["test entry"]})
        with pytest.raises(RuntimeError, match="BERTopic model is required"):
            analyzer.classify_topics()


# topic distribution
class TestTopicDistribution:

    def test_returns_topic_stats(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        assert isinstance(stats, dict)
        # should have at least some topics
        assert len(stats) > 0
        for topic, s in stats.items():
            assert "count" in s
            assert "percentage" in s
            assert s["count"] >= 0
            assert 0 <= s["percentage"] <= 100

    def test_excludes_outliers(self, analyzer):
        """topic_id -1 entries should not appear in distribution"""
        analyzer.df = pd.DataFrame({
            "content": ["normal text", "outlier text"],
            "topic_id": [0, -1],
            "topic_label": ["anxiety", "unclassified"],
        })
        stats = analyzer.analyze_topic_distribution()
        assert "unclassified" not in stats


# outlier analysis
class TestOutlierAnalysis:

    def test_outlier_structure(self, analyzer_with_data):
        outlier = analyzer_with_data.analyze_outlier_distribution()
        assert "outlier_count" in outlier
        assert "outlier_percentage" in outlier
        assert "classified_count" in outlier

    def test_all_classified(self, analyzer):
        """when no outliers, percentage should be 0"""
        analyzer.df = pd.DataFrame({
            "content": ["a", "b"],
            "topic_id": [0, 1],
            "topic_label": ["anxiety", "work"],
            "patient_id": ["p1", "p2"],
        })
        outlier = analyzer.analyze_outlier_distribution()
        assert outlier["outlier_count"] == 0
        assert outlier["outlier_percentage"] == 0


# patient topic coverage
class TestPatientTopicCoverage:

    def test_coverage_structure(self, analyzer_with_data):
        coverage = analyzer_with_data.analyze_patient_topic_coverage()
        # should have entries for patients with classified topics
        assert isinstance(coverage, dict)

    def test_coverage_per_patient(self, analyzer):
        analyzer.df = pd.DataFrame({
            "content": ["text1", "text2", "text3"],
            "topic_id": [0, 1, 0],
            "topic_label": ["anxiety", "work", "anxiety"],
            "patient_id": ["p1", "p1", "p2"],
        })
        coverage = analyzer.analyze_patient_topic_coverage()
        assert "p1" in coverage
        assert coverage["p1"]["num_topics"] == 2
        assert "p2" in coverage


# mitigation notes
class TestMitigationNotes:

    def test_sparse_patients_trigger_representation_bias(self, analyzer_with_data):
        sparse = analyzer_with_data.find_sparse_patients()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        topic_stats = analyzer_with_data.analyze_topic_distribution()
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        outlier_analysis = analyzer_with_data.analyze_outlier_distribution()

        notes = analyzer_with_data.generate_mitigation_notes(
            sparse, temporal, topic_stats, patient_dist, outlier_analysis
        )
        assert any("REPRESENTATION BIAS" in n for n in notes)

    def test_model_not_loaded_note(self, analyzer):
        """should emit a note when model is not loaded"""
        analyzer._model_version = "not_loaded"
        notes = analyzer.generate_mitigation_notes([], {}, {}, {}, {})
        assert any("not loaded" in n for n in notes)

    def test_no_bias_message_when_balanced(self, analyzer):
        analyzer._model_version = "bertopic"
        notes = analyzer.generate_mitigation_notes(
            [], {}, {"topic_a": {"percentage": 30}, "topic_b": {"percentage": 20}}, {}, {}
        )
        assert any("No significant bias" in n for n in notes)


# report
class TestReport:

    def test_report_fields_populated(self, analyzer_with_data):
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        topic_stats = analyzer_with_data.analyze_topic_distribution()
        outlier_analysis = analyzer_with_data.analyze_outlier_distribution()
        sparse = analyzer_with_data.find_sparse_patients()
        coverage = analyzer_with_data.analyze_patient_topic_coverage()
        notes = analyzer_with_data.generate_mitigation_notes(
            sparse, temporal, topic_stats, patient_dist, outlier_analysis
        )

        report = analyzer_with_data.generate_report(
            patient_dist, temporal, topic_stats, outlier_analysis,
            sparse, coverage, notes
        )
        assert isinstance(report, JournalBiasReport)
        assert report.total_records == 5
        assert report.total_patients == 3
        assert report.model_version == "bertopic"


# visualizations
class TestVisualizations:

    def test_generates_png_files(self, analyzer_with_data, tmp_path):
        analyzer_with_data.settings.REPORTS_DIR = tmp_path
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        topic_stats = analyzer_with_data.analyze_topic_distribution()

        paths = analyzer_with_data.generate_visualizations(patient_dist, temporal, topic_stats)
        assert len(paths) >= 2
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"