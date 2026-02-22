# tests for analytics router — patient analytics
# both therapist and patient access with role-based filtering

import pytest
from tests.conftest import PATIENT_ID, PATIENT_2_ID


class TestGetAnalytics:
    """get patient analytics"""

    async def test_get_analytics_as_therapist(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patientId"] == PATIENT_ID
        assert data["totalEntries"] == 25
        assert "themeDistribution" in data
        assert "entryFrequency" in data

    async def test_analytics_theme_distribution(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        themes = data["themeDistribution"]
        assert isinstance(themes, list)
        assert len(themes) > 0
        for t in themes:
            assert "theme" in t
            assert "percentage" in t
            assert "count" in t

    async def test_analytics_entry_frequency(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        freq = data["entryFrequency"]
        assert isinstance(freq, list)
        for f in freq:
            assert "month" in f
            assert "count" in f

    async def test_analytics_date_range(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        dr = data["dateRange"]
        assert dr is not None
        assert "first" in dr
        assert "last" in dr
        assert "spanDays" in dr

    async def test_get_analytics_as_patient_own(self, patient_client):
        resp = await patient_client.get(f"/analytics/{PATIENT_ID}")
        assert resp.status_code == 200

    async def test_patient_cannot_access_other_analytics(self, patient_client):
        resp = await patient_client.get(f"/analytics/{PATIENT_2_ID}")
        assert resp.status_code == 403

    async def test_therapist_cannot_access_unowned_patient(self, therapist_client):
        fake_id = "507f1f77bcf86cd799439099"
        resp = await therapist_client.get(f"/analytics/{fake_id}")
        assert resp.status_code == 403

    async def test_analytics_not_found(self, therapist_client, mock_db):
        # patient exists but has no analytics
        mock_db.patient_analytics._data = []
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        assert resp.status_code == 404
