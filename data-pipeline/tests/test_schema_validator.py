import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock
import pandas as pd
import numpy as np
from validation.schema_validator import SchemaValidator, ExpectationResult, ValidationReport


@pytest.fixture
def validator():
    val = SchemaValidator()
    val.settings = Mock()
    val.settings.PROCESSED_DATA_DIR = Path("/tmp/processed")
    val.settings.REPORTS_DIR = Path("/tmp/reports")
    val.settings.ensure_directories = Mock()
    return val


@pytest.fixture
def sample_conversations_df():
    return pd.DataFrame({
        'conversation_id': ['c1', 'c2', 'c3'],
        'context': ['Question 1', 'Question 2', 'Question 3'],
        'response': ['Answer 1', 'Answer 2', 'Answer 3'],
        'embedding_text': ['Emb 1', 'Emb 2', 'Emb 3'],
        'context_word_count': [5, 10, 8],
        'response_word_count': [8, 12, 10]
    })


@pytest.fixture
def sample_journals_df():
    return pd.DataFrame({
        'journal_id': ['j1', 'j2', 'j3'],
        'patient_id': ['p1', 'p1', 'p2'],
        'therapist_id': ['t1', 't1', 't1'],
        'entry_date': pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03']),
        'content': ['Entry 1', 'Entry 2', 'Entry 3'],
        'word_count': [15, 20, 18]
    })


class TestSchemaValidator:
    
    def test_expect_column_exists_success(self, validator, sample_conversations_df):
        result = validator.expect_column_exists(sample_conversations_df, 'context')
        
        assert isinstance(result, ExpectationResult)
        assert result.success == True
        assert result.details['column'] == 'context'
    
    def test_expect_column_exists_failure(self, validator, sample_conversations_df):
        result = validator.expect_column_exists(sample_conversations_df, 'nonexistent')
        
        assert result.success == False
        assert result.details['found'] == False
    
    def test_expect_column_unique_success(self, validator, sample_conversations_df):
        result = validator.expect_column_unique(sample_conversations_df, 'conversation_id')
        
        assert isinstance(result, ExpectationResult)
        assert result.success == True
        assert result.details['duplicates'] == 0
    
    def test_expect_column_unique_failure(self, validator):
        df = pd.DataFrame({
            'id': ['a', 'b', 'a', 'c']
        })
        result = validator.expect_column_unique(df, 'id')
        
        assert result.success == False
        assert result.details['duplicates'] == 1
    
    def test_expect_column_unique_missing_column(self, validator, sample_conversations_df):
        result = validator.expect_column_unique(sample_conversations_df, 'nonexistent')
        
        assert result.success == False
        assert 'error' in result.details
    
    def test_expect_column_not_null_success(self, validator, sample_conversations_df):
        result = validator.expect_column_not_null(sample_conversations_df, 'context')
        
        assert result.success == True
        assert result.details['null_count'] == 0
    
    def test_expect_column_not_null_failure(self, validator):
        df = pd.DataFrame({
            'col': ['a', None, 'c']
        })
        result = validator.expect_column_not_null(df, 'col')
        
        assert result.success == False
        assert result.details['null_count'] == 1
    
    def test_expect_value_range_success(self, validator, sample_conversations_df):
        result = validator.expect_value_range(
            sample_conversations_df, 
            'context_word_count', 
            min_val=3, 
            max_val=100
        )
        
        assert result.success == True
        assert result.details['violations'] == 0
    
    def test_expect_value_range_min_violation(self, validator):
        df = pd.DataFrame({'score': [1, 5, 10]})
        result = validator.expect_value_range(df, 'score', min_val=3)
        
        assert result.success == False
        assert result.details['violations'] == 1
    
    def test_expect_value_range_max_violation(self, validator):
        df = pd.DataFrame({'score': [5, 10, 150]})
        result = validator.expect_value_range(df, 'score', max_val=100)
        
        assert result.success == False
        assert result.details['violations'] == 1
    
    def test_compute_text_statistics(self, validator, sample_conversations_df):
        stats = validator.compute_text_statistics(sample_conversations_df, 'context')
        
        assert 'context_length_min' in stats
        assert 'context_length_max' in stats
        assert 'context_length_mean' in stats
        assert 'context_words_mean' in stats
        assert stats['context_length_min'] > 0
    
    def test_compute_vocabulary_stats(self, validator):
        df = pd.DataFrame({
            'text': ['hello world', 'world hello', 'test world']
        })
        stats = validator.compute_vocabulary_stats(df, 'text')
        
        assert 'text_total_words' in stats
        assert 'text_unique_words' in stats
        assert 'text_vocab_richness' in stats
        assert stats['text_total_words'] == 6
        assert stats['text_unique_words'] == 3
    
    def test_validate_conversations(self, validator, sample_conversations_df):
        results = validator.validate_conversations(sample_conversations_df)
        
        assert len(results) > 0
        assert all(isinstance(r, ExpectationResult) for r in results)
        # All expectations should pass for valid data
        assert all(r.success for r in results)
    
    def test_validate_conversations_missing_column(self, validator):
        df = pd.DataFrame({
            'conversation_id': ['c1'],
            'context': ['Question']
        })
        results = validator.validate_conversations(df)
        
        # Should have failed expectations for missing columns
        failed = [r for r in results if not r.success]
        assert len(failed) > 0
    
    def test_validate_journals(self, validator, sample_journals_df):
        results = validator.validate_journals(sample_journals_df)
        
        assert len(results) > 0
        assert all(isinstance(r, ExpectationResult) for r in results)
        # All expectations should pass for valid data
        assert all(r.success for r in results)
    
    def test_validate_journals_duplicate_ids(self, validator):
        df = pd.DataFrame({
            'journal_id': ['j1', 'j1', 'j2'],
            'patient_id': ['p1', 'p1', 'p2'],
            'therapist_id': ['t1', 't1', 't1'],
            'entry_date': pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03']),
            'content': ['Entry 1', 'Entry 2', 'Entry 3'],
            'word_count': [15, 20, 18]
        })
        results = validator.validate_journals(df)
        
        # Should fail uniqueness check
        failed = [r for r in results if not r.success and 'unique' in r.name]
        assert len(failed) > 0
    
    def test_generate_report(self, validator, sample_conversations_df):
        results = validator.validate_conversations(sample_conversations_df)
        report = validator.generate_report(
            'test_dataset',
            sample_conversations_df,
            results,
            ['context']
        )
        
        assert isinstance(report, ValidationReport)
        assert report.dataset_name == 'test_dataset'
        assert report.total_records == 3
        assert report.passed > 0
        assert 'record_count' in report.statistics
    
    def test_save_report(self, validator, tmp_path):
        validator.settings.REPORTS_DIR = tmp_path
        report = ValidationReport(
            dataset_name='test',
            timestamp='2025-01-01T00:00:00',
            total_records=10,
            passed=8,
            failed=2,
            expectations=[],
            statistics={}
        )
        
        output_path = validator.save_report(report, 'test_report.json')
        
        assert output_path.exists()
        assert output_path.name == 'test_report.json'