import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import pandas as pd
from bias_detection.slicer import DataSlicer, SliceStats


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'category': ['A', 'A', 'B', 'B', 'C'],
        'score': [10, 20, 30, 40, 50],
        'text': ['anxiety today', 'feeling good', 'very anxious', 'happy day', 'neutral'],
        'value': [1.5, 2.5, 3.5, 4.5, 5.5]
    })


@pytest.fixture
def slicer(sample_df):
    return DataSlicer(sample_df)


class TestDataSlicer:
    
    def test_init(self, sample_df):
        slicer = DataSlicer(sample_df)
        assert slicer.total_count == 5
        assert len(slicer.df) == 5
    
    def test_slice_by_category(self, slicer):
        slices = slicer.slice_by_category('category')
        
        assert len(slices) == 3
        assert 'A' in slices
        assert 'B' in slices
        assert 'C' in slices
        assert len(slices['A']) == 2
        assert len(slices['B']) == 2
        assert len(slices['C']) == 1
    
    def test_slice_by_category_missing_column(self, slicer):
        slices = slicer.slice_by_category('nonexistent')
        assert slices == {}
    
    def test_slice_by_numeric_bins(self, slicer):
        bins = [0, 25, 50, 100]
        labels = ['low', 'medium', 'high']
        
        slices = slicer.slice_by_numeric_bins('score', bins, labels)
        
        assert len(slices) == 3
        assert 'low' in slices
        assert len(slices['low']) == 2  # 10, 20
        assert len(slices['medium']) == 3  # 30, 40, 50 (include_lowest=True includes 50)
        assert len(slices['high']) == 0  # No values above 50
    
    def test_slice_by_numeric_bins_auto_labels(self, slicer):
        bins = [0, 30, 60]
        
        slices = slicer.slice_by_numeric_bins('score', bins)
        
        assert len(slices) == 2
    
    def test_slice_by_keywords(self, slicer):
        keywords = ['anxious', 'anxiety']
        
        result = slicer.slice_by_keywords('text', keywords)
        
        assert len(result) == 2
        assert 'anxiety today' in result['text'].values
        assert 'very anxious' in result['text'].values
    
    def test_slice_by_keywords_case_sensitive(self, slicer):
        keywords = ['Anxiety']
        
        result = slicer.slice_by_keywords('text', keywords, case_sensitive=True)
        
        assert len(result) == 0
    
    def test_slice_by_keyword_groups(self, slicer):
        keyword_groups = {
            'negative': ['anxious', 'anxiety'],
            'positive': ['good', 'happy']
        }
        
        slices = slicer.slice_by_keyword_groups('text', keyword_groups)
        
        assert len(slices) == 2
        assert 'negative' in slices
        assert 'positive' in slices
        assert len(slices['negative']) == 2
        assert len(slices['positive']) == 2
    
    def test_compute_slice_stats(self, slicer, sample_df):
        slice_df = sample_df[sample_df['category'] == 'A']
        
        stats = slicer.compute_slice_stats(slice_df, 'A', ['score'])
        
        assert isinstance(stats, SliceStats)
        assert stats.name == 'A'
        assert stats.count == 2
        assert stats.percentage == 40.0
        assert 'score_mean' in stats.numeric_stats
        assert stats.numeric_stats['score_mean'] == 15.0
    
    def test_compute_slice_stats_no_numeric(self, slicer, sample_df):
        slice_df = sample_df[sample_df['category'] == 'C']
        
        stats = slicer.compute_slice_stats(slice_df, 'C')
        
        assert stats.count == 1
        assert stats.percentage == 20.0
        assert stats.numeric_stats == {}
    
    def test_compute_all_slice_stats(self, slicer):
        slices = slicer.slice_by_category('category')
        
        all_stats = slicer.compute_all_slice_stats(slices, ['score', 'value'])
        
        assert len(all_stats) == 3
        assert all(isinstance(s, SliceStats) for s in all_stats)
        assert all('score_mean' in s.numeric_stats for s in all_stats)
    
    def test_apply_filter(self, slicer):
        result = slicer.apply_filter(lambda df: df['score'] > 25)
        
        assert len(result) == 3
        assert result['score'].min() == 30