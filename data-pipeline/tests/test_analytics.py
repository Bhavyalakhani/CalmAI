import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from analytics.patient_analytics import PatientAnalytics


class TestPatientAnalytics:
    
    def test_classify_themes(self, analytics):
        text = "I feel anxious and my depression is bad"
        themes = analytics.classify_themes(text)
        
        assert "anxiety" in themes
        assert "depression" in themes
    
    def test_classify_themes_no_match(self, analytics):
        text = "just a normal day"
        themes = analytics.classify_themes(text)
        
        assert themes == ["unclassified"]
    
    def test_compute_patient_analytics_empty(self, analytics):
        result = analytics.compute_patient_analytics([])
        
        assert result["total_entries"] == 0
        assert result["theme_distribution"] == {}
    
    def test_compute_patient_analytics_basic(self, analytics, sample_journals):
        result = analytics.compute_patient_analytics(sample_journals)
        
        assert result["total_entries"] == 3
        assert "theme_distribution" in result
        assert "avg_word_count" in result
        assert result["avg_word_count"] > 0
    
    def test_compute_patient_analytics_date_range(self, analytics, sample_journals):
        result = analytics.compute_patient_analytics(sample_journals)
        
        assert "date_range" in result
        assert result["date_range"] is not None
        assert "first" in result["date_range"]
        assert "last" in result["date_range"]
        assert result["date_range"]["span_days"] == 4