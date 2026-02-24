# tests for dashboard router — stats and mood trend
# therapist-only endpoints

import pytest
from tests.conftest import PATIENT_ID, PATIENT_2_ID


class TestDashboardStats:
    """dashboard aggregate stats"""

    async def test_get_stats(self, therapist_client):
        resp = await therapist_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "totalPatients" in data
        assert "totalJournals" in data
        assert "totalConversations" in data
        assert "avgEntriesPerPatient" in data
        assert "activePatients" in data

    async def test_stats_patient_count(self, therapist_client):
        resp = await therapist_client.get("/dashboard/stats")
        data = resp.json()
        assert data["totalPatients"] == 2

    async def test_patient_cannot_access_stats(self, patient_client):
        resp = await patient_client.get("/dashboard/stats")
        assert resp.status_code == 403


class TestMoodTrend:
    """mood trend endpoint"""

    async def test_get_mood_trend(self, therapist_client):
        resp = await therapist_client.get(f"/dashboard/mood-trend/{PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_mood_trend_not_owned(self, therapist_client):
        fake_id = "507f1f77bcf86cd799439099"
        resp = await therapist_client.get(f"/dashboard/mood-trend/{fake_id}")
        assert resp.status_code == 403

    async def test_mood_trend_with_custom_days(self, therapist_client):
        resp = await therapist_client.get(f"/dashboard/mood-trend/{PATIENT_ID}?days=30")
        assert resp.status_code == 200

    async def test_patient_can_access_own_mood_trend(self, patient_client):
        resp = await patient_client.get(f"/dashboard/mood-trend/{PATIENT_ID}")
        assert resp.status_code == 200

    async def test_patient_cannot_access_other_mood_trend(self, patient_client):
        resp = await patient_client.get(f"/dashboard/mood-trend/{PATIENT_2_ID}")
        assert resp.status_code == 403
