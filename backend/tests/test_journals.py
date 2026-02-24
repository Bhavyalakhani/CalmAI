# tests for journals router — list and submit journals
# both therapist and patient access with role-based filtering

import pytest
from bson import ObjectId
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

    async def test_submit_journal_writes_preliminary_to_journals(self, patient_client, mock_db):
        initial_count = len(mock_db.journals._data)
        await patient_client.post("/journals", json={
            "content": "This should appear immediately in the journals collection before DAG 2 runs.",
            "mood": 4,
        })
        assert len(mock_db.journals._data) == initial_count + 1
        doc = mock_db.journals._data[-1]
        assert doc["content"] == "This should appear immediately in the journals collection before DAG 2 runs."
        assert doc["mood"] == 4
        assert doc["is_embedded"] is False
        assert doc["patient_id"] == "patient_001"


class TestAnalyticsRefresh:
    """verify analytics are refreshed instantly on submit, edit, delete"""

    async def test_submit_journal_refreshes_analytics(self, patient_client, mock_db):
        """submitting a journal should update patient_analytics (total_entries, entry_frequency)"""
        old_analytics = await mock_db.patient_analytics.find_one({"patient_id": PATIENT_ID})
        old_total = old_analytics["total_entries"] if old_analytics else 0

        await patient_client.post("/journals", json={
            "content": "Describing my day at length so the analytics refresh picks up this new entry properly.",
            "mood": 3,
        })

        # analytics doc should exist for this patient's pipeline id
        analytics = await mock_db.patient_analytics.find_one({"patient_id": "patient_001"})
        assert analytics is not None
        # total_entries should reflect current journals count for this patient
        assert "total_entries" in analytics
        assert "avg_word_count" in analytics
        assert "updated_at" in analytics

    async def test_delete_journal_refreshes_analytics(self, patient_client, mock_db):
        """deleting a journal should decrement total_entries in patient_analytics"""
        # seed an analytics doc for the pipeline patient id
        mock_db.patient_analytics._data.append({
            "_id": ObjectId(),
            "patient_id": "patient_001",
            "total_entries": 2,
            "topic_distribution": [
                {"topic_id": 0, "label": "anxiety", "keywords": [], "percentage": 100.0, "count": 2},
            ],
            "representative_entries": [
                {"topic_id": 0, "label": "anxiety", "journal_id": "abc123def456", "content": "...", "entry_date": "2025-06-10", "probability": 0.9},
            ],
            "avg_word_count": 11.5,
            "entry_frequency": {"2025-06": 2},
            "date_range": {"first": "2025-06-10", "last": "2025-06-13", "span_days": 3},
        })

        # also put journal patient_id to match pipeline_id for the delete flow
        for j in mock_db.journals._data:
            j["patient_id"] = "patient_001"

        resp = await patient_client.delete("/journals/abc123def456")
        assert resp.status_code == 204

        # check analytics was updated
        analytics = await mock_db.patient_analytics.find_one({"patient_id": "patient_001"})
        assert analytics is not None
        assert analytics["total_entries"] == 1  # was 2, now 1 after delete

        # representative_entries should not contain the deleted journal
        repr_ids = [r["journal_id"] for r in analytics.get("representative_entries", [])]
        assert "abc123def456" not in repr_ids

    async def test_edit_journal_refreshes_analytics(self, patient_client, mock_db):
        """editing a journal should refresh analytics stats"""
        # seed analytics for the pipeline patient
        mock_db.patient_analytics._data.append({
            "_id": ObjectId(),
            "patient_id": "patient_001",
            "total_entries": 2,
            "topic_distribution": [],
            "representative_entries": [],
            "avg_word_count": 11.5,
            "entry_frequency": {"2025-06": 2},
            "date_range": {"first": "2025-06-10", "last": "2025-06-13", "span_days": 3},
        })

        # set pipeline patient_id on journals
        for j in mock_db.journals._data:
            j["patient_id"] = "patient_001"

        resp = await patient_client.patch("/journals/abc123def456", json={
            "content": "I edited this journal to add more detail about my anxiety and how I am coping with it over time.",
            "mood": 3,
        })
        assert resp.status_code == 200

        analytics = await mock_db.patient_analytics.find_one({"patient_id": "patient_001"})
        assert analytics is not None
        # total_entries should still be 2 (edit doesn't change count)
        assert analytics["total_entries"] == 2
        assert "updated_at" in analytics
