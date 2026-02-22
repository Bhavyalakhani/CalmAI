# tests for conversations router — list and filter conversations
# therapist-only endpoints

import pytest
from tests.conftest import PATIENT_ID


class TestListConversations:
    """list and filter conversations"""

    async def test_list_conversations(self, therapist_client):
        resp = await therapist_client.get("/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversations" in data
        assert "total" in data
        assert "page" in data
        assert "pageSize" in data

    async def test_conversations_have_required_fields(self, therapist_client):
        resp = await therapist_client.get("/conversations")
        data = resp.json()
        for conv in data["conversations"]:
            assert "id" in conv
            assert "context" in conv
            assert "response" in conv

    async def test_filter_by_topic(self, therapist_client):
        resp = await therapist_client.get("/conversations?topic=anxiety")
        assert resp.status_code == 200
        data = resp.json()
        for conv in data["conversations"]:
            assert conv.get("topic") == "anxiety"

    async def test_filter_by_severity(self, therapist_client):
        resp = await therapist_client.get("/conversations?severity=moderate")
        assert resp.status_code == 200
        data = resp.json()
        for conv in data["conversations"]:
            assert conv.get("severity") == "moderate"

    async def test_text_search(self, therapist_client):
        resp = await therapist_client.get("/conversations?search=anxious")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0

    async def test_pagination(self, therapist_client):
        resp = await therapist_client.get("/conversations?page=1&pageSize=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["pageSize"] == 5

    async def test_patient_cannot_list_conversations(self, patient_client):
        resp = await patient_client.get("/conversations")
        assert resp.status_code == 403
