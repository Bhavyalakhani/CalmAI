# tests for conversation_bias.py
# covers model-based topic classification, severity (priority order),
# distributions, underrepresentation, cross analysis, outlier analysis,
# mitigations, report, and visualizations

import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np

from bias_detection.conversation_bias import ConversationBiasAnalyzer, BiasReport


def _make_mock_inference(topics=None, probs=None, labels=None):
    """helper — creates a mock TopicModelInference with realistic behavior"""
    mock = MagicMock()
    mock.load.return_value = True
    mock.is_loaded = True

    _topics = topics or [0, 1, 0, 2]
    _probs = probs if probs is not None else np.array([0.85, 0.72, 0.91, 0.65])
    _labels = labels or {0: "Anxiety & Worry", 1: "Depression & Mood", 2: "Crisis & Safety", -1: "Outlier"}

    mock.predict.return_value = (_topics, _probs)
    mock.get_topic_label.side_effect = lambda tid: _labels.get(tid, f"Topic {tid}")
    mock.get_topic_keywords.return_value = ["feel", "anxious", "worried"]
    mock.get_all_topic_info.return_value = [
        {"topic_id": 0, "count": 20, "label": "Anxiety & Worry", "keywords": ["anxious", "worried"]},
        {"topic_id": 1, "count": 15, "label": "Depression & Mood", "keywords": ["depressed", "sad"]},
        {"topic_id": 2, "count": 10, "label": "Crisis & Safety", "keywords": ["crisis", "safety"]},
    ]

    return mock


def _make_mock_severity_inference(severities=None):
    """helper — creates a mock severity TopicModelInference"""
    mock = MagicMock()
    mock.load.return_value = True
    mock.is_loaded = True
    _severities = severities or ["moderate", "severe", "moderate", "crisis"]
    mock.predict_severity.return_value = _severities
    return mock


@pytest.fixture
def analyzer(mock_settings):
    a = ConversationBiasAnalyzer()
    a.settings = mock_settings
    # use mock model for tests
    mock_inf = _make_mock_inference()
    a._inference = mock_inf
    a._model_loaded = True
    a._model_version = "bertopic"
    return a


@pytest.fixture
def analyzer_with_data(analyzer, conversations_df):
    """analyzer that already has data loaded and classified (model-based)"""
    analyzer.df = conversations_df.copy()
    from bias_detection.slicer import DataSlicer
    analyzer.slicer = DataSlicer(analyzer.df)
    analyzer.classify_topics()
    # mock the severity model for classify_severity
    with patch("topic_modeling.inference.TopicModelInference") as MockSeverity:
        mock_sev = _make_mock_severity_inference()
        MockSeverity.return_value = mock_sev
        analyzer.classify_severity()
    return analyzer


# model-based topic classification
class TestModelClassifyTopics:

    def test_creates_topic_columns(self, analyzer_with_data):
        assert "topic_id" in analyzer_with_data.df.columns
        assert "topic_label" in analyzer_with_data.df.columns
        assert "topic_probability" in analyzer_with_data.df.columns

    def test_model_labels_assigned(self, analyzer_with_data):
        df = analyzer_with_data.df
        # row 0: topic 0 → "Anxiety & Worry"
        assert df.iloc[0]["topic_label"] == "Anxiety & Worry"
        assert df.iloc[0]["topic_id"] == 0

    def test_depression_assigned(self, analyzer_with_data):
        df = analyzer_with_data.df
        # row 1: topic 1 → "Depression & Mood"
        assert df.iloc[1]["topic_label"] == "Depression & Mood"
        assert df.iloc[1]["topic_id"] == 1

    def test_raises_when_no_model(self, analyzer):
        """should raise RuntimeError when model is not available"""
        analyzer._model_loaded = False
        analyzer._inference = None
        analyzer.df = pd.DataFrame({"context": ["test text"]})
        with pytest.raises(RuntimeError, match="BERTopic model is required"):
            analyzer.classify_topics()


# severity classification (bertopic severity model)
class TestClassifySeverity:

    def test_severity_assigned_from_model(self, analyzer_with_data):
        df = analyzer_with_data.df
        # row 3: mock returns "crisis" for 4th element
        assert df.iloc[3]["severity"] == "crisis"
        # row 1: mock returns "severe" for 2nd element
        assert df.iloc[1]["severity"] == "severe"

    def test_fallback_when_no_model(self, analyzer):
        analyzer.df = pd.DataFrame({"context": ["just chatting about nothing"]})
        # when model load fails, all get "unknown"
        with patch("topic_modeling.inference.TopicModelInference") as MockSeverity:
            mock_sev = MagicMock()
            mock_sev.load.return_value = False
            MockSeverity.return_value = mock_sev
            analyzer.classify_severity()
        assert analyzer.df.iloc[0]["severity"] == "unknown"


# topic distribution
class TestTopicDistribution:

    def test_returns_stats_per_topic(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        # model-based: topics from mock inference
        assert len(stats) > 0
        first_topic = list(stats.values())[0]
        assert "count" in first_topic
        assert "percentage" in first_topic
        assert "response_length_mean" in first_topic

    def test_excludes_outliers(self, analyzer):
        analyzer.df = pd.DataFrame({
            "context": ["just nothing"],
            "response_word_count": [10],
            "topic_id": [-1],
            "topic_label": ["unclassified"],
            "topic_probability": [0.0],
            "severity": ["unknown"],
        })
        stats = analyzer.analyze_topic_distribution()
        assert len(stats) == 0


# severity distribution
class TestSeverityDistribution:

    def test_includes_all_severity_levels(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_severity_distribution()
        for level in ["crisis", "severe", "moderate", "mild", "unknown"]:
            assert level in stats

    def test_counts_sum_to_total(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_severity_distribution()
        total = sum(s["count"] for s in stats.values())
        assert total == len(analyzer_with_data.df)


# underrepresentation
class TestUnderrepresented:

    def test_finds_low_percentage_topics(self, analyzer):
        # create data where some topics are underrepresented
        # use mock model that assigns topic 0 to most, topic 3 to last
        mock_inf = _make_mock_inference(
            topics=[0] * 50 + [3],
            probs=np.array([0.9] * 50 + [0.7]),
            labels={0: "Anxiety & Worry", 3: "Rare Topic", -1: "Outlier"},
        )
        analyzer._inference = mock_inf
        analyzer._model_loaded = True
        analyzer.df = pd.DataFrame({
            "context": ["I feel anxious"] * 50 + ["rare topic text"],
            "response_word_count": [50] * 51,
        })
        analyzer.classify_topics()
        stats = analyzer.analyze_topic_distribution()
        under = analyzer.find_underrepresented_topics(stats)
        assert isinstance(under, list)
        # rare topic at ~2% should be underrepresented
        assert "Rare Topic" in under

    def test_no_underrepresented_when_balanced(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        under = analyzer_with_data.find_underrepresented_topics(stats)
        # 4 rows, 3 classified at 25% each → none underrepresented
        assert len(under) == 0


# cross analysis
class TestCrossAnalysis:

    def test_has_overall_mean(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        cross = analyzer_with_data.cross_analyze(stats)
        assert "overall_response_mean" in cross
        assert cross["overall_response_mean"] > 0

    def test_shorter_longer_lists_exist(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        cross = analyzer_with_data.cross_analyze(stats)
        assert "shorter_response_topics" in cross
        assert "longer_response_topics" in cross


# outlier analysis (replaces topic_overlap)
class TestOutlierAnalysis:

    def test_outlier_stats_present(self, analyzer_with_data):
        outlier = analyzer_with_data.analyze_outlier_distribution()
        assert "outlier_count" in outlier
        assert "outlier_percentage" in outlier
        assert "classified_count" in outlier

    def test_all_outliers(self, analyzer):
        analyzer.df = pd.DataFrame({
            "context": ["abc", "def"],
            "topic_id": [-1, -1],
            "topic_label": ["unclassified", "unclassified"],
            "topic_probability": [0.0, 0.0],
        })
        outlier = analyzer.analyze_outlier_distribution()
        assert outlier["outlier_count"] == 2
        assert outlier["outlier_percentage"] == 100.0
        assert outlier["classified_count"] == 0


# mitigation notes
class TestMitigationNotes:

    def test_includes_representation_bias_label(self, analyzer):
        # force underrepresented topics
        notes = analyzer.generate_mitigation_notes(
            ["grief", "identity"],
            {"shorter_response_topics": [], "longer_response_topics": []},
            {"outlier_percentage": 0},
        )
        assert any("REPRESENTATION BIAS" in n for n in notes)

    def test_no_bias_message_when_all_balanced(self, analyzer):
        analyzer._model_version = "bertopic"
        notes = analyzer.generate_mitigation_notes(
            [], {"shorter_response_topics": [], "longer_response_topics": []}, {"outlier_percentage": 0}
        )
        assert len(notes) == 1
        assert "No significant bias" in notes[0]

    def test_model_not_loaded_note(self, analyzer):
        analyzer._model_version = "not_loaded"
        notes = analyzer.generate_mitigation_notes(
            [], {"shorter_response_topics": [], "longer_response_topics": []}, {"outlier_percentage": 0}
        )
        assert any("not loaded" in n for n in notes)


# report
class TestReport:

    def test_report_fields(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        severity = analyzer_with_data.analyze_severity_distribution()
        under = analyzer_with_data.find_underrepresented_topics(stats)
        cross = analyzer_with_data.cross_analyze(stats)
        outlier = analyzer_with_data.analyze_outlier_distribution()
        notes = analyzer_with_data.generate_mitigation_notes(under, cross, outlier)

        report = analyzer_with_data.generate_report(stats, severity, under, cross, outlier, notes)
        assert isinstance(report, BiasReport)
        assert report.dataset_name == "conversations"
        assert report.total_records == 4
        assert report.model_version == "bertopic"
        assert isinstance(report.underrepresented_topics, list)
        assert isinstance(report.outlier_analysis, dict)
        assert isinstance(report.topic_distribution, dict)


# visualizations
class TestVisualizations:

    def test_generates_png_files(self, analyzer_with_data, tmp_path):
        analyzer_with_data.settings.REPORTS_DIR = tmp_path
        stats = analyzer_with_data.analyze_topic_distribution()
        severity = analyzer_with_data.analyze_severity_distribution()

        paths = analyzer_with_data.generate_visualizations(stats, severity)
        assert len(paths) == 3
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"