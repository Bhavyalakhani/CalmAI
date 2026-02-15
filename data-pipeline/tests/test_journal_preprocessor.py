import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock
import pandas as pd
from datetime import datetime
from preprocessing.journal_preprocessor import JournalPreprocessor


@pytest.fixture
def preprocessor():
    prep = JournalPreprocessor()
    prep.settings = Mock()
    prep.settings.RAW_DATA_DIR = Path("/tmp/raw")
    prep.settings.PROCESSED_DATA_DIR = Path("/tmp/processed")
    prep.settings.ensure_directories = Mock()
    return prep


@pytest.fixture
def sample_journal_df():
    return pd.DataFrame({
        'journal_id': ['j1', 'j2', 'j3'],
        'patient_id': ['p1', 'p1', 'p2'],
        'content': ['Feeling anxious today', 'Had a good day', 'Work stress'],
        'entry_date': ['2025-01-01', '2025-01-03', '2025-01-02']
    })


class TestJournalPreprocessor:
    
    def test_parse_dates(self, preprocessor, sample_journal_df):
        preprocessor.df = sample_journal_df.copy()
        result = preprocessor.parse_dates()
        
        assert pd.api.types.is_datetime64_any_dtype(result['entry_date'])
        assert result['entry_date'].iloc[0] == pd.Timestamp('2025-01-01')
    
    def test_parse_dates_with_invalid(self, preprocessor):
        df = pd.DataFrame({
            'entry_date': ['2025-01-01', 'invalid', '2025-01-03']
        })
        preprocessor.df = df
        result = preprocessor.parse_dates()
        
        assert pd.isna(result['entry_date'].iloc[1])
        assert pd.notna(result['entry_date'].iloc[0])
    
    def test_apply_preprocessing(self, preprocessor, sample_journal_df):
        preprocessor.df = sample_journal_df.copy()
        preprocessor.preprocessor = Mock()
        preprocessor.preprocessor.process = lambda x: x.strip().lower()
        
        mock_stats = Mock()
        mock_stats.word_count = 3
        mock_stats.char_count = 20
        mock_stats.sentence_count = 1
        preprocessor.preprocessor.compute_statistics = Mock(return_value=mock_stats)
        
        result = preprocessor.apply_preprocessing()
        
        assert 'word_count' in result.columns
        assert 'char_count' in result.columns
        assert 'sentence_count' in result.columns
    
    def test_add_temporal_features(self, preprocessor, sample_journal_df):
        preprocessor.df = sample_journal_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.add_temporal_features()
        
        assert 'day_of_week' in result.columns
        assert 'month' in result.columns
        assert 'year' in result.columns
        assert result['month'].iloc[0] == 1
        assert result['year'].iloc[0] == 2025
    
    def test_calculate_days_since_last(self, preprocessor, sample_journal_df):
        preprocessor.df = sample_journal_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.calculate_days_since_last()
        
        assert 'days_since_last' in result.columns
        # First entry for each patient should have 0
        assert result[result['patient_id'] == 'p1']['days_since_last'].iloc[0] == 0
        # Second entry should have difference
        assert result[result['patient_id'] == 'p1']['days_since_last'].iloc[1] == 2
    
    def test_create_embedding_text(self, preprocessor, sample_journal_df):
        preprocessor.df = sample_journal_df.copy()
        preprocessor.parse_dates()
        result = preprocessor.create_embedding_text()
        
        assert 'embedding_text' in result.columns
        assert '2025-01-01' in result['embedding_text'].iloc[0]
        assert 'Feeling anxious today' in result['embedding_text'].iloc[0]
    
    def test_create_embedding_text_no_date(self, preprocessor):
        df = pd.DataFrame({
            'content': ['Test content'],
            'entry_date': [pd.NaT]
        })
        preprocessor.df = df
        result = preprocessor.create_embedding_text()
        
        assert result['embedding_text'].iloc[0] == 'Test content'
    
    def test_validate_removes_duplicates(self, preprocessor):
        df = pd.DataFrame({
            'journal_id': ['j1', 'j1', 'j2'],
            'patient_id': ['p1', 'p1', 'p2'],
            'content': ['Content 1', 'Content 1', 'Content 2']
        })
        preprocessor.df = df
        preprocessor.validate()
        
        assert len(preprocessor.df) == 2
        assert len(preprocessor.df['journal_id'].unique()) == 2
    
    def test_validate_removes_empty_content(self, preprocessor):
        df = pd.DataFrame({
            'journal_id': ['j1', 'j2', 'j3'],
            'patient_id': ['p1', 'p1', 'p2'],
            'content': ['Valid content', '  ', 'Another valid']
        })
        preprocessor.df = df
        preprocessor.validate()
        
        assert len(preprocessor.df) == 2
    
    def test_validate_missing_columns(self, preprocessor):
        df = pd.DataFrame({'content': ['Test']})
        preprocessor.df = df
        
        with pytest.raises(ValueError, match="Missing required columns"):
            preprocessor.validate()
    
    def test_save(self, preprocessor, sample_journal_df, tmp_path):
        preprocessor.df = sample_journal_df.copy()
        preprocessor.settings.PROCESSED_DATA_DIR = tmp_path
        
        output_path = preprocessor.save()
        
        assert output_path.exists()
        loaded = pd.read_parquet(output_path)
        assert len(loaded) == 3