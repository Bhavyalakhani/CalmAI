# tests for journal_bias.py
# covers patient distribution, sparse patients, temporal patterns,
# theme classification, theme distribution, theme overlap, mitigation notes, report, viz

import pytest
from unittest.mock import patch, Mock
from pathlib import Path
import pandas as pd
import numpy as np

from bias_detection.journal_bias import JournalBiasAnalyzer, JournalBiasReport


@pytest.fixture
def analyzer(mock_settings):
    a = JournalBiasAnalyzer()
    a.settings = mock_settings
    return a


@pytest.fixture
def analyzer_with_data(analyzer, journals_df):
    """analyzer that already has data loaded and classified"""
    analyzer.df = journals_df.copy()
    from bias_detection.slicer import DataSlicer
    analyzer.slicer = DataSlicer(analyzer.df)
    analyzer.classify_themes()
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


# theme classification
class TestClassifyThemes:

    def test_creates_theme_columns(self, analyzer_with_data):
        for theme in analyzer_with_data.THEMES:
            assert f"theme_{theme}" in analyzer_with_data.df.columns

    def test_anxiety_detected(self, analyzer_with_data):
        # row 0: "Feeling anxious about tomorrow"
        assert analyzer_with_data.df.iloc[0]["theme_anxiety"] == True

    def test_therapy_detected(self, analyzer_with_data):
        # row 3: "Therapy session was helpful"
        assert analyzer_with_data.df.iloc[3]["theme_therapy"] == True


# theme distribution
class TestThemeDistribution:

    def test_returns_all_themes(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_theme_distribution()
        assert "anxiety" in stats
        assert "positive" in stats
        assert "work" in stats

    def test_counts_are_non_negative(self, analyzer_with_data):
        stats = analyzer_with_data.analyze_theme_distribution()
        for theme, s in stats.items():
            assert s["count"] >= 0
            assert 0 <= s["percentage"] <= 100


# theme overlap
class TestThemeOverlap:

    def test_overlap_structure(self, analyzer_with_data):
        overlap = analyzer_with_data.analyze_theme_overlap()
        assert "multi_theme_count" in overlap
        assert "no_theme_count" in overlap
        assert "top_co_occurrences" in overlap

    def test_multi_theme_when_content_matches_several(self, analyzer):
        # edge case: content hits multiple themes
        analyzer.df = pd.DataFrame({"content": ["I feel anxious and depressed about work"]})
        analyzer.classify_themes()
        overlap = analyzer.analyze_theme_overlap()
        assert overlap["multi_theme_count"] == 1


# mitigation notes
class TestMitigationNotes:

    def test_sparse_patients_trigger_representation_bias(self, analyzer_with_data):
        sparse = analyzer_with_data.find_sparse_patients()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        theme_stats = analyzer_with_data.analyze_theme_distribution()
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        theme_overlap = analyzer_with_data.analyze_theme_overlap()

        notes = analyzer_with_data.generate_mitigation_notes(
            sparse, temporal, theme_stats, patient_dist, theme_overlap
        )
        assert any("REPRESENTATION BIAS" in n for n in notes)

    def test_low_positive_triggers_measurement_bias(self, analyzer):
        # edge case: no positive entries at all
        theme_stats = {"positive": {"percentage": 0}, "negative": {"percentage": 10}}
        notes = analyzer.generate_mitigation_notes(
            [], {}, theme_stats, {}, {}
        )
        assert any("MEASUREMENT BIAS" in n for n in notes)

    def test_no_bias_message_when_balanced(self, analyzer):
        notes = analyzer.generate_mitigation_notes(
            [], {}, {"positive": {"percentage": 30}, "negative": {"percentage": 20}}, {}, {}
        )
        assert any("No significant bias" in n for n in notes)


# report
class TestReport:

    def test_report_fields_populated(self, analyzer_with_data):
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        theme_stats = analyzer_with_data.analyze_theme_distribution()
        theme_overlap = analyzer_with_data.analyze_theme_overlap()
        sparse = analyzer_with_data.find_sparse_patients()
        notes = analyzer_with_data.generate_mitigation_notes(sparse, temporal, theme_stats, patient_dist, theme_overlap)

        report = analyzer_with_data.generate_report(
            patient_dist, temporal, theme_stats, theme_overlap, sparse, notes
        )
        assert isinstance(report, JournalBiasReport)
        assert report.total_records == 5
        assert report.total_patients == 3


# visualizations
class TestVisualizations:

    def test_generates_png_files(self, analyzer_with_data, tmp_path):
        analyzer_with_data.settings.REPORTS_DIR = tmp_path
        patient_dist = analyzer_with_data.analyze_patient_distribution()
        temporal = analyzer_with_data.analyze_temporal_patterns()
        theme_stats = analyzer_with_data.analyze_theme_distribution()

        paths = analyzer_with_data.generate_visualizations(patient_dist, temporal, theme_stats)
        assert len(paths) >= 2
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"
