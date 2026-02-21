import pytest
from unittest.mock import patch


@patch("preprocessing.journal_preprocessor.config")
def test_process_incoming_journals(mock_config, mock_settings):
    """process_incoming_journals should preprocess and return records list"""
    mock_config.settings = mock_settings

    from preprocessing.journal_preprocessor import process_incoming_journals

    journals = [
        {
            "journal_id": "j1",
            "patient_id": "p1",
            "content": "Today I felt anxious but did some breathing.",
            "entry_date": "2025-01-01",
        }
    ]

    records = process_incoming_journals(journals)
    assert isinstance(records, list)
    assert len(records) == 1
    rec = records[0]
    assert rec.get("journal_id") == "j1"
    assert "embedding_text" in rec
    # entry_date must be serialized as string (JSON-safe)
    assert isinstance(rec.get("entry_date"), (str, type(None)))


@patch("preprocessing.journal_preprocessor.config")
def test_process_incoming_journals_empty(mock_config, mock_settings):
    mock_config.settings = mock_settings
    from preprocessing.journal_preprocessor import process_incoming_journals
    assert process_incoming_journals([]) == []
