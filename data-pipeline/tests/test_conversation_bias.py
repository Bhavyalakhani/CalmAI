# tests for conversation_bias.py
# covers topic classification, severity (priority order), distributions,
# underrepresentation, cross analysis, topic overlap, mitigations, report, and viz

import pytest
from unittest.mock import patch, Mock
from pathlib import Path
import pandas as pd
import numpy as np

from bias_detection.conversation_bias import ConversationBiasAnalyzer, BiasReport


@pytest.fixture
def analyzer(mock_settings):
    a = ConversationBiasAnalyzer()
    a.settings = mock_settings
    return a


@pytest.fixture
def analyzer_with_data(analyzer, conversations_df):
    """analyzer that already has data loaded and classified"""
    analyzer.df = conversations_df.copy()
    from bias_detection.slicer import DataSlicer
    analyzer.slicer = DataSlicer(analyzer.df)
    analyzer.classify_topics()
    analyzer.classify_severity()
    return analyzer


# topic classification
class TestClassifyTopics:

    def test_creates_topic_columns(self, analyzer_with_data):
        # should have boolean columns for each topic
        for topic in analyzer_with_data.TOPICS:
            assert f"topic_{topic}" in analyzer_with_data.df.columns

    def test_anxiety_detected_correctly(self, analyzer_with_data):
        df = analyzer_with_data.df
        # row 0 mentions "anxious and worried" → should match anxiety
        assert df.iloc[0]["topic_anxiety"] == True
        # row 2 is about partner fight → should not match anxiety
        assert df.iloc[2]["topic_anxiety"] == False


# severity classification
class TestClassifySeverity:

    def test_severity_priority_order(self, analyzer_with_data):
        df = analyzer_with_data.df
        # row 1 says "can't cope" (severe) and row 3 says "kill myself" (crisis)
        # "can't cope" also matches moderate ("struggling"? no just "can't cope")
        # crisis should override any lower severity
        assert df.iloc[3]["severity"] == "crisis"
        assert df.iloc[1]["severity"] == "severe"

    def test_no_keywords_gives_unknown(self, analyzer):
        analyzer.df = pd.DataFrame({"context": ["just chatting about nothing"]})
        analyzer.classify_severity()
        assert analyzer.df.iloc[0]["severity"] == "unknown"


# topic distribution
class TestTopicDistribution:

    def test_returns_stats_per_topic(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        assert "anxiety" in stats
        assert "count" in stats["anxiety"]
        assert "percentage" in stats["anxiety"]
        assert "response_length_mean" in stats["anxiety"]

    def test_percentages_are_reasonable(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        total_pct = sum(s["percentage"] for s in stats.values())
        # topics can overlap, so total can exceed 100, but each should be <= 100
        for topic, s in stats.items():
            assert 0 <= s["percentage"] <= 100


# severity distribution
class TestSeverityDistribution:

    def test_includes_all_severity_levels(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_severity_distribution()
        for level in ["crisis", "severe", "moderate", "mild", "unknown"]:
            assert level in stats

    def test_uses_data_slicer(self, analyzer_with_data):
        # just making sure it doesn't explode — the slicer is used internally
        stats = analyzer_with_data.analyze_severity_distribution()
        total = sum(s["count"] for s in stats.values())
        assert total == len(analyzer_with_data.df)


# underrepresentation
class TestUnderrepresented:

    def test_finds_low_percentage_topics(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        under = analyzer_with_data.find_underrepresented_topics(stats)
        # with only 4 rows, topics with 0 matches are at 0% → underrepresented
        assert isinstance(under, list)
        # identity, grief, substance should all be at 0%
        assert "identity" in under
        assert "grief" in under


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


# topic overlap
class TestTopicOverlap:

    def test_overlap_stats_present(self, analyzer_with_data):
        overlap = analyzer_with_data.analyze_topic_overlap()
        assert "multi_topic_count" in overlap
        assert "no_topic_count" in overlap
        assert "top_co_occurrences" in overlap

    def test_multi_topic_when_context_matches_multiple(self, analyzer):
        # edge case: one row matches both anxiety and work
        analyzer.df = pd.DataFrame({
            "context": ["I feel anxious about my job and work"],
            "response": ["That must be stressful"],
            "response_word_count": [10],
        })
        analyzer.classify_topics()
        overlap = analyzer.analyze_topic_overlap()
        assert overlap["multi_topic_count"] == 1


# mitigation notes
class TestMitigationNotes:

    def test_includes_representation_bias_label(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        under = analyzer_with_data.find_underrepresented_topics(stats)
        cross = analyzer_with_data.cross_analyze(stats)
        overlap = analyzer_with_data.analyze_topic_overlap()
        notes = analyzer_with_data.generate_mitigation_notes(under, cross, overlap)

        # should flag underrepresented topics with REPRESENTATION BIAS label
        assert any("REPRESENTATION BIAS" in n for n in notes)

    def test_no_bias_message_when_all_balanced(self, analyzer):
        # edge case: nothing to flag → default message
        notes = analyzer.generate_mitigation_notes([], {"shorter_response_topics": [], "longer_response_topics": []}, {})
        assert len(notes) == 1
        assert "No significant bias" in notes[0]


# report
class TestReport:

    def test_report_fields(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_topic_distribution()
        severity = analyzer_with_data.analyze_severity_distribution()
        under = analyzer_with_data.find_underrepresented_topics(stats)
        cross = analyzer_with_data.cross_analyze(stats)
        overlap = analyzer_with_data.analyze_topic_overlap()
        notes = analyzer_with_data.generate_mitigation_notes(under, cross, overlap)

        report = analyzer_with_data.generate_report(stats, severity, under, cross, overlap, notes)
        assert isinstance(report, BiasReport)
        assert report.dataset_name == "conversations"
        assert report.total_records == 4
        assert len(report.underrepresented_topics) > 0


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


# topic overlap (NEW)
class TestTopicOverlap:

    def test_overlap_stats_present(self, analyzer_with_data):
        overlap = analyzer_with_data.analyze_topic_overlap()
        assert "multi_topic_count" in overlap
        assert "no_topic_count" in overlap
        assert "top_co_occurrences" in overlap

    def test_multi_topic_when_context_matches_multiple(self, analyzer):
        analyzer.df = pd.DataFrame({
            "context": ["I feel anxious about my job and work"],
            "response": ["That must be stressful"],
            "response_word_count": [10],
        })
        analyzer.classify_topics()
        overlap = analyzer.analyze_topic_overlap()
        assert overlap["multi_topic_count"] == 1