import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from bias_detection.conversation_bias import ConversationBiasAnalyzer, BiasReport


@pytest.fixture
def analyzer():
    ana = ConversationBiasAnalyzer()
    ana.settings = Mock()
    ana.settings.PROCESSED_DATA_DIR = Path("/tmp/processed")
    ana.settings.REPORTS_DIR = Path("/tmp/reports")
    ana.settings.ensure_directories = Mock()
    return ana


@pytest.fixture
def sample_conversations_df():
    return pd.DataFrame({
        'conversation_id': ['c1', 'c2', 'c3', 'c4'],
        'context': [
            'I feel anxious and worried about work',
            "My depression is terrible and I can't cope",
            'Had a fight with my partner',
            'I want to kill myself'
        ],
        'response': ['Response 1', 'Response 2', 'Response 3', 'Response 4'],
        'response_word_count': [50, 60, 55, 100]
    })


class TestConversationBiasAnalyzer:
    
    def test_classify_topics(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        result = analyzer.classify_topics()
        
        assert 'topic_anxiety' in result.columns
        assert 'topic_depression' in result.columns
        assert result['topic_anxiety'].iloc[0] == True
        assert result['topic_depression'].iloc[1] == True
    
    def test_classify_severity(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        result = analyzer.classify_severity()
        
        assert 'severity' in result.columns
        # Row 3 has "kill myself" which should match crisis
        assert result['severity'].iloc[3] == 'crisis'
        # Row 1 has "cannot cope" which should match severe
        assert result['severity'].iloc[1] == 'severe'
    
    def test_analyze_topic_distribution(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        analyzer.classify_topics()
        
        topic_stats = analyzer.analyze_topic_distribution()
        
        assert 'anxiety' in topic_stats
        assert topic_stats['anxiety']['count'] >= 0
        assert 'percentage' in topic_stats['anxiety']
        assert 'response_length_mean' in topic_stats['anxiety']
    
    def test_analyze_severity_distribution(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        analyzer.classify_severity()
        
        severity_stats = analyzer.analyze_severity_distribution()
        
        assert 'crisis' in severity_stats
        assert 'unknown' in severity_stats
        assert severity_stats['crisis']['count'] >= 0
    
    def test_find_underrepresented_topics(self, analyzer):
        topic_stats = {
            'anxiety': {'percentage': 2.0},
            'depression': {'percentage': 5.0},
            'work': {'percentage': 1.5}
        }
        
        underrepresented = analyzer.find_underrepresented_topics(topic_stats)
        
        assert 'anxiety' in underrepresented
        assert 'work' in underrepresented
        assert 'depression' not in underrepresented
    
    def test_cross_analyze(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        analyzer.classify_topics()
        topic_stats = analyzer.analyze_topic_distribution()
        
        cross_analysis = analyzer.cross_analyze(topic_stats)
        
        assert 'overall_response_mean' in cross_analysis
        assert 'shorter_response_topics' in cross_analysis
        assert 'longer_response_topics' in cross_analysis
    
    def test_generate_mitigation_notes(self, analyzer):
        underrepresented = ['trauma', 'grief']
        cross_analysis = {
            'shorter_response_topics': [
                {'topic': 'anxiety', 'response_mean': 30, 'diff_from_overall': -25}
            ],
            'longer_response_topics': []
        }
        
        notes = analyzer.generate_mitigation_notes(underrepresented, cross_analysis)
        
        assert len(notes) == 2
        assert 'trauma' in notes[0]
        assert 'anxiety' in notes[1]
    
    def test_generate_report(self, analyzer, sample_conversations_df):
        analyzer.df = sample_conversations_df.copy()
        
        report = analyzer.generate_report(
            topic_stats={'anxiety': {'count': 1, 'percentage': 25.0}},
            severity_stats={'crisis': {'count': 1, 'percentage': 25.0}},
            underrepresented=['trauma'],
            cross_analysis={'overall_response_mean': 50},
            mitigation_notes=['Note 1']
        )
        
        assert isinstance(report, BiasReport)
        assert report.dataset_name == 'conversations'
        assert report.total_records == 4
        assert len(report.underrepresented_topics) == 1
    
    @patch('bias_detection.conversation_bias.plt')
    def test_generate_visualizations(self, mock_plt, analyzer, tmp_path):
        analyzer.settings.REPORTS_DIR = tmp_path
        reports_dir = tmp_path / "bias"
        reports_dir.mkdir()
        
        topic_stats = {
            'anxiety': {'percentage': 25.0, 'response_length_mean': 50},
            'depression': {'percentage': 25.0, 'response_length_mean': 60}
        }
        severity_stats = {
            'crisis': {'count': 1},
            'moderate': {'count': 2}
        }
        
        paths = analyzer.generate_visualizations(topic_stats, severity_stats)
        
        assert len(paths) == 3
        assert mock_plt.savefig.call_count == 3