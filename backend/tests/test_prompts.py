# tests for the prompts router
# covers create, fetch pending, fetch all, respond via journal, and validations

import pytest
from httpx import AsyncClient

from tests.conftest import THERAPIST_ID, PATIENT_ID, PATIENT_2_ID


# create prompt

class TestCreatePrompt:
    """POST /prompts"""

    @pytest.mark.asyncio
    async def test_create_prompt_success(self, therapist_client: AsyncClient):
        res = await therapist_client.post("/prompts", json={
            "patientId": PATIENT_ID,
            "promptText": "Reflect on a moment this week where you felt at peace.",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["patientId"] == PATIENT_ID
        assert data["therapistId"] == THERAPIST_ID
        assert data["status"] == "pending"
        assert data["promptText"] == "Reflect on a moment this week where you felt at peace."
        assert data["promptId"]
        assert data["createdAt"]
        assert data["responseJournalId"] is None

    @pytest.mark.asyncio
    async def test_create_prompt_wrong_patient(self, therapist_client: AsyncClient):
        res = await therapist_client.post("/prompts", json={
            "patientId": "nonexistent-patient-id",
            "promptText": "Write about your day.",
        })
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_create_prompt_patient_forbidden(self, patient_client: AsyncClient):
        res = await patient_client.post("/prompts", json={
            "patientId": PATIENT_ID,
            "promptText": "This should fail.",
        })
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_create_prompt_text_too_short(self, therapist_client: AsyncClient):
        res = await therapist_client.post("/prompts", json={
            "patientId": PATIENT_ID,
            "promptText": "Hi",
        })
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_create_prompt_missing_patient(self, therapist_client: AsyncClient):
        res = await therapist_client.post("/prompts", json={
            "promptText": "Write about your feelings.",
        })
        assert res.status_code == 422


# fetch pending prompts

class TestFetchPrompts:
    """GET /prompts/{patient_id}"""

    @pytest.mark.asyncio
    async def test_patient_sees_own_prompts(self, patient_client: AsyncClient, mock_db):
        # seed a prompt
        mock_db.prompts._data.append({
            "prompt_id": "p-test-001",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "patient_id": PATIENT_ID,
            "prompt_text": "What made you smile today?",
            "created_at": "2026-02-20T10:00:00Z",
            "status": "pending",
            "response_journal_id": None,
            "response_content": None,
            "responded_at": None,
        })
        res = await patient_client.get(f"/prompts/{PATIENT_ID}")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["promptId"] == "p-test-001"
        assert data[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_patient_cannot_see_others_prompts(self, patient_client: AsyncClient):
        res = await patient_client.get(f"/prompts/{PATIENT_2_ID}")
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_therapist_sees_patient_prompts(self, therapist_client: AsyncClient, mock_db):
        mock_db.prompts._data.append({
            "prompt_id": "p-test-002",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "patient_id": PATIENT_ID,
            "prompt_text": "Describe your sleep this week.",
            "created_at": "2026-02-19T10:00:00Z",
            "status": "pending",
            "response_journal_id": None,
            "response_content": None,
            "responded_at": None,
        })
        res = await therapist_client.get(f"/prompts/{PATIENT_ID}")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, patient_client: AsyncClient, mock_db):
        mock_db.prompts._data.extend([
            {
                "prompt_id": "p-pending",
                "therapist_id": THERAPIST_ID,
                "therapist_name": "Dr. Sarah Chen",
                "patient_id": PATIENT_ID,
                "prompt_text": "Pending prompt.",
                "created_at": "2026-02-20T10:00:00Z",
                "status": "pending",
                "response_journal_id": None,
                "response_content": None,
                "responded_at": None,
            },
            {
                "prompt_id": "p-responded",
                "therapist_id": THERAPIST_ID,
                "therapist_name": "Dr. Sarah Chen",
                "patient_id": PATIENT_ID,
                "prompt_text": "Responded prompt.",
                "created_at": "2026-02-18T10:00:00Z",
                "status": "responded",
                "response_journal_id": "j-resp-001",
                "response_content": "My response.",
                "responded_at": "2026-02-19T10:00:00Z",
            },
        ])
        res = await patient_client.get(f"/prompts/{PATIENT_ID}?status=pending")
        assert res.status_code == 200
        data = res.json()
        assert all(p["status"] == "pending" for p in data)


# fetch all prompts (therapist)

class TestFetchAllPrompts:
    """GET /prompts/{patient_id}/all"""

    @pytest.mark.asyncio
    async def test_therapist_gets_all_with_responses(self, therapist_client: AsyncClient, mock_db):
        mock_db.prompts._data.append({
            "prompt_id": "p-all-001",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "patient_id": PATIENT_ID,
            "prompt_text": "How was your week?",
            "created_at": "2026-02-15T10:00:00Z",
            "status": "responded",
            "response_journal_id": "abc123def456",
            "response_content": None,
            "responded_at": "2026-02-16T10:00:00Z",
        })
        res = await therapist_client.get(f"/prompts/{PATIENT_ID}/all")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        responded = [p for p in data if p["status"] == "responded"]
        assert len(responded) >= 1

    @pytest.mark.asyncio
    async def test_patient_cannot_access_all(self, patient_client: AsyncClient):
        res = await patient_client.get(f"/prompts/{PATIENT_ID}/all")
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_therapist_wrong_patient(self, therapist_client: AsyncClient):
        res = await therapist_client.get("/prompts/nonexistent-id/all")
        assert res.status_code == 403


# respond via journal submission

class TestPromptResponseViaJournal:
    """POST /journals with promptId"""

    @pytest.mark.asyncio
    async def test_submit_with_prompt_id_links_prompt(self, patient_client: AsyncClient, mock_db):
        mock_db.prompts._data.append({
            "prompt_id": "p-link-001",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "patient_id": PATIENT_ID,
            "prompt_text": "What are you grateful for?",
            "created_at": "2026-02-20T10:00:00Z",
            "status": "pending",
            "response_journal_id": None,
            "response_content": None,
            "responded_at": None,
        })
        res = await patient_client.post("/journals", json={
            "content": "I am grateful for my morning walks and the quiet time I get to reflect.",
            "mood": 4,
            "promptId": "p-link-001",
        })
        assert res.status_code == 201

        # verify prompt was updated
        prompt = mock_db.prompts._data[0]
        assert prompt["status"] == "responded"
        assert prompt["response_journal_id"] is not None
        assert prompt["responded_at"] is not None

    @pytest.mark.asyncio
    async def test_submit_without_prompt_id(self, patient_client: AsyncClient, mock_db):
        res = await patient_client.post("/journals", json={
            "content": "Just a regular journal entry about my day at the park.",
            "mood": 3,
        })
        assert res.status_code == 201
        data = res.json()
        assert data["journalId"]

    @pytest.mark.asyncio
    async def test_submit_with_nonexistent_prompt_still_succeeds(self, patient_client: AsyncClient, mock_db):
        """journal submission should succeed even if prompt_id doesn't match anything"""
        res = await patient_client.post("/journals", json={
            "content": "Entry with a bad prompt id but the journal should still save.",
            "mood": 2,
            "promptId": "nonexistent-prompt",
        })
        assert res.status_code == 201
