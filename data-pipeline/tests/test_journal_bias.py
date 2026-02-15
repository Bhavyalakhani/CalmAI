import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from bias_detection.journal_bias import JournalBiasAnalyzer, JournalBiasReport


@pytest.fixture
def analyzer():
    ana = JournalBiasAnalyzer()
    ana.settings = Mock()
    ana.settings.PROCESSED_DATA_DIR = Path("/tmp/processed")
    ana.settings.REPORTS_DIR = Path("/tmp/reports")
    ana.settings.ensure_directories = Mock()
    return ana


@pytest.fixture
def sample_journals_df():
    return pd.DataFrame({
        'journal_id': ['j1', 'j2', 'j3', 'j4', 'j5'],
        'patient_id': ['p1', 'p1', 'p2', 'p2', 'p3'],
        'content': [
            'Feeling anxious about tomorrow',
            'Had a good day today',
            'Depressed and struggling',
            'Therapy session was helpful',
            'Work is stressful'
        ],
        'word_count': [20, 15, 18, 22, 16],
        'day_of_week': [0, 1, 2, 3, 4],
        'month': [1, 1, 2, 2, 3],
        'days_since_last': [0, 3, 0, 5, 0]
    })


class TestJournalBiasAnalyzer:
    
    def test_analyze_patient_distribution(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        
        dist = analyzer.analyze_patient_distribution()
        
        # The method counts unique patients from groupby
        assert dist['total_patients'] == 2  # p1 and p2 have 2 entries each
        assert 'entries_per_patient_mean' in dist
        assert 'entries_per_patient_std' in dist
        assert dist['entries_per_patient_min'] == 1
        assert dist['entries_per_patient_max'] == 2
    
    def test_find_sparse_patients(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        analyzer.SPARSE_THRESHOLD = 2
        
        sparse = analyzer.find_sparse_patients()
        
        assert len(sparse) == 1
        assert sparse[0]['patient_id'] == 'p3'
        assert sparse[0]['entry_count'] == 1
    
    def test_analyze_temporal_patterns(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        
        temporal = analyzer.analyze_temporal_patterns()
        
        assert 'entries_by_day' in temporal
        assert 'entries_by_month' in temporal
        assert 'entry_gap_mean' in temporal
        assert len(temporal['entries_by_day']) == 5
    
    def test_classify_themes(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        result = analyzer.classify_themes()
        
        assert 'theme_anxiety' in result.columns
        assert 'theme_positive' in result.columns
        assert 'theme_depression' in result.columns
        assert result['theme_anxiety'].iloc[0] == True
        assert result['theme_positive'].iloc[1] == True
    
    def test_analyze_theme_distribution(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        analyzer.classify_themes()
        
        theme_stats = analyzer.analyze_theme_distribution()
        
        assert 'anxiety' in theme_stats
        assert 'positive' in theme_stats
        assert theme_stats['anxiety']['count'] >= 0
        assert 'percentage' in theme_stats['anxiety']
        assert 'word_count_mean' in theme_stats['anxiety']
    
    def test_generate_mitigation_notes(self, analyzer):
        sparse_patients = [{'patient_id': 'p1', 'entry_count': 5}]
        temporal = {'entry_gap_max': 45}
        theme_stats = {
            'positive': {'percentage': 5.0},
            'negative': {'percentage': 60.0}
        }
        
        notes = analyzer.generate_mitigation_notes(sparse_patients, temporal, theme_stats)
        
        # Should generate 4 notes: sparse patients, gap, low positive, high negative
        assert len(notes) == 4
        assert any('sparse' in note.lower() or 'fewer' in note.lower() for note in notes)
        assert any('45' in note for note in notes)
        assert any('positive' in note.lower() for note in notes)
        assert any('negative' in note.lower() for note in notes)
    
    def test_generate_report(self, analyzer, sample_journals_df):
        analyzer.df = sample_journals_df.copy()
        
        report = analyzer.generate_report(
            patient_dist={'total_patients': 3},
            temporal={'entry_gap_mean': 3.5},
            theme_stats={'anxiety': {'count': 1, 'percentage': 20.0}},
            sparse_patients=[],
            mitigation_notes=['Note 1']
        )
        
        assert isinstance(report, JournalBiasReport)
        assert report.dataset_name == 'journals'
        assert report.total_records == 5
        assert report.total_patients == 3
    
    @patch('bias_detection.journal_bias.plt')
    def test_generate_visualizations(self, mock_plt, analyzer, tmp_path):
        analyzer.settings.REPORTS_DIR = tmp_path
        reports_dir = tmp_path / "bias"
        reports_dir.mkdir()
        
        patient_dist = {'total_patients': 3}
        temporal = {
            'entries_by_day': {'Monday': 1, 'Tuesday': 1},
            'entries_by_month': {1: 2, 2: 2}
        }
        theme_stats = {
            'anxiety': {'percentage': 20.0, 'word_count_mean': 18},
            'positive': {'percentage': 20.0, 'word_count_mean': 15}
        }
        
        paths = analyzer.generate_visualizations(patient_dist, temporal, theme_stats)
        
        assert len(paths) == 3
        assert mock_plt.savefig.call_count == 3