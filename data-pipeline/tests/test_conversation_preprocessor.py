import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from preprocessing.conversation_preprocessor import ConversationPreprocessor


@pytest.fixture
def preprocessor():
    prep = ConversationPreprocessor()
    prep.settings = Mock()
    prep.settings.RAW_DATA_DIR = Path("/tmp/raw")
    prep.settings.PROCESSED_DATA_DIR = Path("/tmp/processed")
    prep.settings.ensure_directories = Mock()
    return prep


@pytest.fixture
def sample_conversation_df():
    return pd.DataFrame({
        'Context': ['I feel anxious about work', 'Help with depression'],
        'Response': ['Here is some advice', 'I understand your feelings'],
        'QuestionTitle': ['Anxiety', 'Depression']
    })


class TestConversationPreprocessor:
    
    def test_standardize_columns(self, preprocessor, sample_conversation_df):
        preprocessor.df = sample_conversation_df.copy()
        result = preprocessor.standardize_columns()
        
        assert 'context' in result.columns
        assert 'response' in result.columns
        assert 'Context' not in result.columns
    
    def test_standardize_columns_with_questiontext(self, preprocessor):
        df = pd.DataFrame({
            'questiontext': ['Question 1', 'Question 2'],
            'questiontitle': ['Title 1', 'Title 2'],
            'answertext': ['Answer 1', 'Answer 2']
        })
        preprocessor.df = df
        result = preprocessor.standardize_columns()
        
        assert 'context' in result.columns
        assert 'response' in result.columns
        assert 'context_title' in result.columns
    
    def test_generate_ids(self, preprocessor):
        df = pd.DataFrame({
            'context': ['Question 1', 'Question 2', 'Question 1'],
            'response': ['Answer 1', 'Answer 2', 'Answer 1']
        })
        preprocessor.df = df
        result = preprocessor.generate_ids()
        
        assert 'conversation_id' in result.columns
        assert len(result) == 2  # Duplicate removed
        assert len(result['conversation_id'].unique()) == 2
    
    def test_apply_preprocessing(self, preprocessor):
        df = pd.DataFrame({
            'context': ['  Hello world  ', 'Test message'],
            'response': ['Response one', 'Response two']
        })
        preprocessor.df = df
        preprocessor.preprocessor = Mock()
        preprocessor.preprocessor.process = lambda x: x.strip().lower()
        
        # Mock compute_statistics to return objects with attributes
        mock_stats = Mock()
        mock_stats.word_count = 2
        mock_stats.char_count = 10
        preprocessor.preprocessor.compute_statistics = Mock(return_value=mock_stats)
        
        result = preprocessor.apply_preprocessing()
        
        assert 'context_word_count' in result.columns
        assert 'context_char_count' in result.columns
        assert 'response_word_count' in result.columns
    
    def test_create_embedding_text(self, preprocessor):
        df = pd.DataFrame({
            'context': ['I need help', 'Feeling sad'],
            'response': ['I can help you', 'That must be hard']
        })
        preprocessor.df = df
        result = preprocessor.create_embedding_text()
        
        assert 'embedding_text' in result.columns
        assert 'User concern:' in result['embedding_text'].iloc[0]
        assert 'Counselor response:' in result['embedding_text'].iloc[0]
    
    def test_validate_filters_invalid(self, preprocessor):
        df = pd.DataFrame({
            'context': ['Good question here', '', 'Hi there'],
            'response': ['Good answer here', 'Short answer', ''],
            'context_word_count': [3, 0, 2],
            'response_word_count': [3, 2, 0]
        })
        preprocessor.df = df
        preprocessor.validate()
        
        # Only first row meets all criteria (>= 3 words in both)
        assert len(preprocessor.df) == 1
        assert preprocessor.df['context'].iloc[0] == 'Good question here'
    
    def test_validate_all_valid(self, preprocessor):
        df = pd.DataFrame({
            'context': ['Good question', 'Another question'],
            'response': ['Good answer', 'Another answer'],
            'context_word_count': [5, 6],
            'response_word_count': [5, 6]
        })
        preprocessor.df = df
        result = preprocessor.validate()
        
        assert result is True
        assert len(preprocessor.df) == 2
    
    @patch('preprocessing.conversation_preprocessor.pd.read_parquet')
    def test_load_data(self, mock_read_parquet, preprocessor, tmp_path, sample_conversation_df):
        input_dir = tmp_path / "conversations"
        input_dir.mkdir()
        
        # Create mock parquet files
        file1 = input_dir / "file1.parquet"
        file2 = input_dir / "file2.parquet"
        file1.touch()
        file2.touch()
        
        preprocessor.settings.RAW_DATA_DIR = tmp_path
        mock_read_parquet.return_value = sample_conversation_df
        
        result = preprocessor.load_data()
        
        assert len(result) == 4  # 2 files × 2 rows
        assert 'source_file' in result.columns
    
    def test_save(self, preprocessor, tmp_path):
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        preprocessor.df = df
        preprocessor.settings.PROCESSED_DATA_DIR = tmp_path
        
        output_path = preprocessor.save()
        
        assert output_path.exists()
        loaded = pd.read_parquet(output_path)
        assert len(loaded) == 2