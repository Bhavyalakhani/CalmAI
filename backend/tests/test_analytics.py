# tests for analytics router — patient analytics
# both therapist and patient access with role-based filtering
# supports new bertopic topic_distribution format

import pytest
from tests.conftest import PATIENT_ID, PATIENT_2_ID


class TestCleanLabel:
    """unit tests for _clean_label helper"""

    def test_clean_plain_string(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("anxiety & stress") == "anxiety & stress"

    def test_clean_topic_prefix(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("topic: Sleep Quality") == "Sleep Quality"

    def test_clean_stringified_list(self):
        from app.routers.analytics import _clean_label
        raw = "['topic: Partner support for self-care', '', '', '', '']"
        assert _clean_label(raw) == "Partner support for self-care"

    def test_clean_stringified_list_no_prefix(self):
        from app.routers.analytics import _clean_label
        raw = "['Sleep Patterns and Mental Impact', '', '']"
        assert _clean_label(raw) == "Sleep Patterns and Mental Impact"

    def test_clean_empty_list(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("['', '', '']") == "['', '', '']"

    def test_clean_empty_string(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("") == ""

    def test_clean_topic_24_fallback(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("Topic 24") == "Miscellaneous"

    def test_clean_topic_111_fallback(self):
        from app.routers.analytics import _clean_label
        assert _clean_label("Topic 111") == "Miscellaneous"

    def test_clean_topic_prefix_with_number(self):
        from app.routers.analytics import _clean_label
        # "topic: Topic 5" — prefix stripped first, then number detected
        assert _clean_label("topic: Topic 5") == "Miscellaneous"

    def test_clean_topic_number_not_plain_word(self):
        from app.routers.analytics import _clean_label
        # actual meaningful label should not match
        assert _clean_label("Topic Modeling Results") == "Topic Modeling Results"


class TestGetAnalytics:
    """get patient analytics"""

    async def test_get_analytics_as_therapist(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patientId"] == PATIENT_ID
        assert data["totalEntries"] == 25
        assert "topicDistribution" in data
        assert "entryFrequency" in data

    async def test_analytics_topic_distribution(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        topics = data["topicDistribution"]
        assert isinstance(topics, list)
        assert len(topics) > 0
        for t in topics:
            assert "topicId" in t
            assert "label" in t
            assert "keywords" in t
            assert "percentage" in t
            assert "count" in t

    async def test_analytics_topics_over_time(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        tot = data["topicsOverTime"]
        assert isinstance(tot, list)
        assert len(tot) > 0
        for item in tot:
            assert "month" in item
            assert "topicId" in item
            assert "label" in item
            assert "frequency" in item

    async def test_analytics_representative_entries(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        reps = data["representativeEntries"]
        assert isinstance(reps, list)
        assert len(reps) > 0
        for r in reps:
            assert "topicId" in r
            assert "label" in r
            assert "content" in r

    async def test_analytics_model_version(self, therapist_client):
        resp = await therapist_client.get(f"/analytics/{PATIENT_ID}")
        data = resp.json()
        assert data["modelVersion"] == "v1.0_20250614"

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
