# tests for generate_journals.py
# covers json parsing (clean, markdown-wrapped, malformed), entry processing,
# raw response saving, and skip-existing logic for the gemini api

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

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
        "start_date": "2025-01-01",
    }


# date calculation
class TestDateCalc:

    def test_end_date_is_300_days_later(self, generator):
        # start_date + 300 days = 2025-10-28
        assert generator.get_end_date("2025-01-01") == "2025-10-28"

    def test_end_date_with_leap_year(self, generator):
        # 2024 is a leap year, make sure it doesn't break
        result = generator.get_end_date("2024-01-01")
        assert result == "2024-10-27"


# json parsing
class TestJsonParsing:

    def test_parses_clean_json(self, generator):
        raw = '[{"entry_number": 1, "date": "2025-01-01", "content": "Test entry"}]'
        result = generator.parse_json_response(raw)

        assert len(result) == 1
        assert result[0]["content"] == "Test entry"

    def test_strips_markdown_fences(self, generator):
        # gemini often wraps json in ```json ... ```
        raw = '```json\n[{"entry_number": 1, "date": "2025-01-01", "content": "Test"}]\n```'
        result = generator.parse_json_response(raw)
        assert len(result) == 1

    def test_handles_single_object_instead_of_array(self, generator):
        # edge case: model returns a single dict instead of a list
        raw = '{"entry_number": 1, "date": "2025-01-01", "content": "Test entry"}'
        result = generator.parse_json_response(raw)
        assert result["entry_number"] == 1

    def test_raises_on_totally_broken_json(self, generator):
        # edge case: complete garbage
        with pytest.raises(json.JSONDecodeError):
            generator.parse_json_response("not json at all {{{")


# entry processing
class TestEntryProcessing:

    def test_creates_proper_journal_entries(self, generator):
        parsed = [
            {"entry_number": 1, "date": "2025-01-01", "content": "First entry"},
            {"entry_number": 2, "date": "2025-01-03", "content": "Second entry"},
        ]
        result = generator.process_entries(parsed, "P001", "T001")

        assert len(result) == 2
        assert result[0]["journal_id"] == "P001_entry_001"
        assert result[0]["patient_id"] == "P001"
        assert result[0]["therapist_id"] == "T001"
        assert result[0]["word_count"] == 2

    def test_skips_entries_with_empty_content(self, generator):
        parsed = [
            {"entry_number": 1, "date": "2025-01-01", "content": "Valid entry"},
            {"entry_number": 2, "date": "2025-01-02", "content": ""},
        ]
        result = generator.process_entries(parsed, "P001", "T001")
        assert len(result) == 1

    def test_handles_alternative_key_names(self, generator):
        # gemini sometimes uses different key names like entryNumber or text
        parsed = [{"entryNumber": 1, "entry_date": "2025-01-01", "text": "Test"}]
        result = generator.process_entries(parsed, "P001", "T001")

        assert len(result) == 1
        assert result[0]["content"] == "Test"

    def test_returns_empty_list_for_no_valid_entries(self, generator):
        # edge case: all entries have empty content
        parsed = [
            {"entry_number": 1, "date": "2025-01-01", "content": ""},
            {"entry_number": 2, "date": "2025-01-02", "content": ""},
        ]
        result = generator.process_entries(parsed, "P001", "T001")
        assert result == []


# save raw response
class TestSaveRaw:

    def test_saves_json_to_disk(self, generator, tmp_path):
        generator.settings.RAW_DATA_DIR = tmp_path
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        output = generator.save_raw_response("P001", "test response", raw_dir)

        assert output.exists()
        with open(output) as f:
            data = json.load(f)
        assert data["patient_id"] == "P001"
        assert data["raw_response"] == "test response"
        assert "timestamp" in data


# fetch patient response
class TestFetchResponse:

    def test_returns_model_response_text(self, generator, sample_patient):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = '{"result": "success"}'
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client

        result = generator.fetch_patient_response(sample_patient)

        assert result == '{"result": "success"}'
        mock_client.models.generate_content.assert_called_once()


# skip existing
class TestSkipExisting:

    @patch.object(JournalGenerator, "load_config")
    @patch.object(JournalGenerator, "fetch_patient_response")
    @patch.object(JournalGenerator, "save_raw_response")
    def test_does_not_refetch_existing_files(self, mock_save, mock_fetch, mock_load,
                                              generator, tmp_path, sample_patient):
        generator.settings.RAW_DATA_DIR = tmp_path
        generator.settings.ensure_directories = Mock()
        generator.cfg = {"patients": [sample_patient]}
        mock_load.return_value = generator.cfg

        # simulate an existing raw file
        raw_dir = tmp_path / "journals" / "raw_responses"
        raw_dir.mkdir(parents=True)
        (raw_dir / "P001_raw.json").touch()

        generator.client = Mock()
        generator.fetch_all(skip_existing=True)

        mock_fetch.assert_not_called()
