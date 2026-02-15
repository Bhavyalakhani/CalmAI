import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import pandas as pd
from acquisition.generate_journals import JournalGenerator


@pytest.fixture
def generator():
    gen = JournalGenerator()
    gen.settings = Mock()
    gen.settings.RAW_DATA_DIR = Path("/tmp/data")
    gen.settings.CONFIGS_DIR = Path("/tmp/configs")
    gen.settings.GEMINI_API_KEY = "test_key"
    gen.settings.GEMINI_MODEL = "gemini-model"
    gen.logger = Mock()
    return gen


@pytest.fixture
def sample_patient():
    return {
        "patient_id": "P001",
        "name": "John Doe",
        "age": 30,
        "occupation": "Engineer",
        "background": "Test background",
        "concerns": ["anxiety", "stress"],
        "writing_style": "casual",
        "start_date": "2025-01-01"
    }


class TestJournalGenerator:
    
    def test_get_end_date(self, generator):
        result = generator.get_end_date("2025-01-01")
        assert result == "2025-10-28"
    
    def test_parse_json_response_clean(self, generator):
        json_text = '[{"entry_number": 1, "date": "2025-01-01", "content": "Test entry"}]'
        result = generator.parse_json_response(json_text)
        
        assert len(result) == 1
        assert result[0]["entry_number"] == 1
        assert result[0]["content"] == "Test entry"
    
    def test_parse_json_response_with_markdown(self, generator):
        json_text = '```json\n[{"entry_number": 1, "date": "2025-01-01", "content": "Test"}]\n```'
        result = generator.parse_json_response(json_text)
        
        assert len(result) == 1
        assert result[0]["entry_number"] == 1
    
    def test_parse_json_response_regex_fallback(self, generator):
        malformed = '{"entry_number": 1, "date": "2025-01-01", "content": "Test entry"}'
        result = generator.parse_json_response(malformed)
        
        # Single dict gets parsed as valid JSON
        assert result["entry_number"] == 1
        assert result["content"] == "Test entry"
    
    def test_process_entries(self, generator):
        parsed = [
            {"entry_number": 1, "date": "2025-01-01", "content": "First entry"},
            {"entry_number": 2, "date": "2025-01-03", "content": "Second entry"}
        ]
        
        result = generator.process_entries(parsed, "P001", "T001")
        
        assert len(result) == 2
        assert result[0]["journal_id"] == "P001_entry_001"
        assert result[0]["patient_id"] == "P001"
        assert result[0]["therapist_id"] == "T001"
        assert result[0]["word_count"] == 2
    
    def test_process_entries_skip_empty(self, generator):
        parsed = [
            {"entry_number": 1, "date": "2025-01-01", "content": "Valid entry"},
            {"entry_number": 2, "date": "2025-01-02", "content": ""}
        ]
        
        result = generator.process_entries(parsed, "P001", "T001")
        
        assert len(result) == 1
    
    def test_process_entries_alternative_keys(self, generator):
        parsed = [
            {"entryNumber": 1, "entry_date": "2025-01-01", "text": "Test"}
        ]
        
        result = generator.process_entries(parsed, "P001", "T001")
        
        assert len(result) == 1
        assert result[0]["content"] == "Test"
    
    @patch('acquisition.generate_journals.genai.Client')
    def test_fetch_patient_response_success(self, mock_client_class, generator, sample_patient):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = '{"result": "success"}'
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client
        
        result = generator.fetch_patient_response(sample_patient)
        
        assert result == '{"result": "success"}'
        mock_client.models.generate_content.assert_called_once()
    
    def test_save_raw_response(self, generator, tmp_path):
        generator.settings.RAW_DATA_DIR = tmp_path
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        output = generator.save_raw_response("P001", "test response", raw_dir)
        
        assert output.exists()
        with open(output) as f:
            data = json.load(f)
        assert data["patient_id"] == "P001"
        assert data["raw_response"] == "test response"
    
    @patch.object(JournalGenerator, 'load_config')
    @patch.object(JournalGenerator, 'fetch_patient_response')
    @patch.object(JournalGenerator, 'save_raw_response')
    def test_fetch_all_skip_existing(self, mock_save, mock_fetch, mock_load, 
                                     generator, tmp_path, sample_patient):
        generator.settings.RAW_DATA_DIR = tmp_path
        generator.settings.ensure_directories = Mock()
        generator.cfg = {"patients": [sample_patient]}
        mock_load.return_value = generator.cfg
        
        raw_dir = tmp_path / "journals" / "raw_responses"
        raw_dir.mkdir(parents=True)
        existing = raw_dir / "P001_raw.json"
        existing.touch()
        
        generator.client = Mock()
        result = generator.fetch_all(skip_existing=True)
        
        mock_fetch.assert_not_called()
