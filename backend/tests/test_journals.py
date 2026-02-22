# tests for journals router — list and submit journals
# both therapist and patient access with role-based filtering

import pytest
from tests.conftest import PATIENT_ID, PATIENT_2_ID, THERAPIST_ID


class TestListJournals:
    """list journal entries"""

    async def test_list_journals_as_therapist(self, therapist_client):
        resp = await therapist_client.get("/journals")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # therapist sees journals for their patients
        assert len(data) >= 1

    async def test_list_journals_with_patient_filter(self, therapist_client):
        resp = await therapist_client.get(f"/journals?patientId={PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        for journal in data:
            assert journal["patientId"] == PATIENT_ID

    async def test_list_journals_as_patient_own_only(self, patient_client):
        resp = await patient_client.get("/journals")
        assert resp.status_code == 200
        data = resp.json()
        for journal in data:
            assert journal["patientId"] == PATIENT_ID

    async def test_journal_response_has_fields(self, therapist_client):
        resp = await therapist_client.get("/journals")
        data = resp.json()
        if data:
            journal = data[0]
            assert "id" in journal
            assert "patientId" in journal
            assert "content" in journal
            assert "entryDate" in journal
            assert "themes" in journal
            assert "wordCount" in journal

    async def test_list_journals_with_pagination(self, therapist_client):
        resp = await therapist_client.get("/journals?limit=1&skip=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 1

    async def test_therapist_cannot_access_unowned_patient(self, therapist_client):
        fake_patient = "507f1f77bcf86cd799439099"
        resp = await therapist_client.get(f"/journals?patientId={fake_patient}")
        assert resp.status_code == 403


class TestSubmitJournal:
    """submit new journal entries"""

    async def test_submit_journal_as_patient(self, patient_client):
        resp = await patient_client.post("/journals", json={
            "content": "Today I practiced the breathing exercises my therapist recommended. I felt calmer after.",
            "mood": 4,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "journalId" in data
        assert "message" in data

    async def test_submit_journal_too_short(self, patient_client):
        resp = await patient_client.post("/journals", json={
            "content": "Hi",
        })
        assert resp.status_code == 422

    async def test_submit_journal_no_mood(self, patient_client):
        resp = await patient_client.post("/journals", json={
            "content": "Writing without a mood score, just reflecting on my day and how things went.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "journalId" in data

    async def test_therapist_cannot_submit_journal(self, therapist_client):
        resp = await therapist_client.post("/journals", json={
            "content": "Therapist trying to submit a journal entry which should not be allowed.",
        })
        assert resp.status_code == 403

    async def test_submit_journal_writes_to_incoming(self, patient_client, mock_db):
        initial_count = len(mock_db.incoming_journals._data)
        await patient_client.post("/journals", json={
            "content": "Testing that this goes to the incoming_journals collection for pipeline processing.",
            "mood": 3,
        })
        assert len(mock_db.incoming_journals._data) == initial_count + 1
        doc = mock_db.incoming_journals._data[-1]
        assert doc["is_processed"] is False
        # journal submit uses pipeline_patient_id for consistency with data pipeline
        assert doc["patient_id"] == "patient_001"
