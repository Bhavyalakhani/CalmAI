# tests for search router and rag service — vector search + answer generation
# therapist-only endpoints

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from tests.conftest import PATIENT_ID
from app.services.rag_service import _format_context, _extract_sources, _format_history
from app.routers.journals import _classify_themes


class TestRagSearch:
    """rag-powered search endpoint"""

    async def test_rag_search_success(self, therapist_client):
        """test rag search with mocked embedding and llm"""
        mock_results = {
            "query": "anxiety coping",
            "results": [
                {
                    "content": "Patient expressed anxiety about work.",
                    "score": 0.92,
                    "source": "journal",
                    "metadata": {"patient_id": PATIENT_ID, "entry_date": "2025-06-10"},
                },
            ],
            "generated_answer": "Based on the retrieved documents, the patient has expressed anxiety related to work.",
            "sources": ["journal:patient_001:2025-06-10"],
        }

        with patch("app.routers.search.search", new_callable=AsyncMock, return_value=mock_results):
            resp = await therapist_client.post("/search/rag", json={
                "query": "anxiety coping",
                "topK": 5,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["query"] == "anxiety coping"
            assert len(data["results"]) == 1
            assert data["generatedAnswer"] is not None
            assert len(data["sources"]) == 1

    async def test_rag_search_with_patient_filter(self, therapist_client):
        mock_results = {
            "query": "sleep patterns",
            "results": [],
            "generated_answer": None,
            "sources": [],
        }

        with patch("app.routers.search.search", new_callable=AsyncMock, return_value=mock_results) as mock_search:
            resp = await therapist_client.post("/search/rag", json={
                "query": "sleep patterns",
                "patientId": PATIENT_ID,
                "topK": 3,
            })
            assert resp.status_code == 200
            # verify pipeline_patient_id was resolved and passed to search
            call_kwargs = mock_search.call_args
            assert call_kwargs.kwargs.get("patient_id") == "patient_001"

    async def test_rag_search_patient_not_owned(self, therapist_client):
        fake_id = "507f1f77bcf86cd799439099"
        resp = await therapist_client.post("/search/rag", json={
            "query": "test query",
            "patientId": fake_id,
        })
        assert resp.status_code == 403

    async def test_patient_cannot_search(self, patient_client):
        resp = await patient_client.post("/search/rag", json={
            "query": "my entries",
        })
        assert resp.status_code == 403

    async def test_rag_search_with_source_type(self, therapist_client):
        mock_results = {
            "query": "therapy progress",
            "results": [],
            "generated_answer": None,
            "sources": [],
        }

        with patch("app.routers.search.search", new_callable=AsyncMock, return_value=mock_results):
            resp = await therapist_client.post("/search/rag", json={
                "query": "therapy progress",
                "sourceType": "journal",
            })
            assert resp.status_code == 200

    async def test_rag_search_empty_query_rejected(self, therapist_client):
        resp = await therapist_client.post("/search/rag", json={
            "query": "",
        })
        assert resp.status_code == 422


class TestFormatContext:
    """rag service helper: format retrieved docs into context string"""

    def test_format_context_journal(self):
        results = [{
            "content": "I felt anxious today.",
            "doc_type": "journal",
            "metadata": {"patient_id": "p1", "entry_date": "2025-06-10"},
            "score": 0.95,
        }]
        context = _format_context(results)
        assert "[Source 1]" in context
        assert "Journal entry" in context
        assert "p1" in context
        assert "2025-06-10" in context

    def test_format_context_conversation(self):
        results = [{
            "content": "Therapist response text.",
            "doc_type": "conversation",
            "metadata": {"conversation_id": "conv123"},
            "score": 0.88,
        }]
        context = _format_context(results)
        assert "Therapy conversation" in context
        assert "conv123" in context

    def test_format_context_empty(self):
        context = _format_context([])
        assert "No relevant documents" in context

    def test_format_context_multiple(self):
        results = [
            {"content": "Doc 1", "doc_type": "journal", "metadata": {}, "score": 0.9},
            {"content": "Doc 2", "doc_type": "conversation", "metadata": {}, "score": 0.8},
        ]
        context = _format_context(results)
        assert "[Source 1]" in context
        assert "[Source 2]" in context
        assert "---" in context


class TestExtractSources:
    """rag service helper: extract source ids"""

    def test_extract_journal_source(self):
        results = [{"doc_type": "journal", "metadata": {"patient_id": "p1", "entry_date": "2025-01-01"}}]
        sources = _extract_sources(results)
        assert sources == ["journal:p1:2025-01-01"]

    def test_extract_conversation_source(self):
        results = [{"doc_type": "conversation", "metadata": {"conversation_id": "c1"}}]
        sources = _extract_sources(results)
        assert sources == ["conversation:c1"]

    def test_extract_unknown_source(self):
        results = [{"doc_type": "other", "metadata": {}}]
        sources = _extract_sources(results)
        assert sources == ["other:unknown"]

    def test_extract_multiple(self):
        results = [
            {"doc_type": "journal", "metadata": {"patient_id": "p1", "entry_date": "2025-01-01"}},
            {"doc_type": "conversation", "metadata": {"conversation_id": "c1"}},
        ]
        sources = _extract_sources(results)
        assert len(sources) == 2


class TestFormatHistory:
    """rag service helper: format conversation history for follow-up prompts"""

    def test_empty_history(self):
        assert _format_history([]) == ""

    def test_single_turn(self):
        history = [
            {"role": "user", "content": "What themes appear?"},
            {"role": "assistant", "content": "I found anxiety themes."},
        ]
        result = _format_history(history)
        assert "Therapist: What themes appear?" in result
        assert "Assistant: I found anxiety themes." in result

    def test_multiple_turns(self):
        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
        ]
        result = _format_history(history)
        assert result.count("Therapist:") == 2
        assert result.count("Assistant:") == 2

    def test_truncates_to_max_turns(self):
        # create more than MAX_HISTORY_TURNS messages
        history = [{"role": "user", "content": f"msg {i}"} for i in range(15)]
        result = _format_history(history)
        # should only contain last 10 messages
        assert "msg 5" in result
        assert "msg 14" in result


class TestRagSearchWithHistory:
    """rag search endpoint with conversation history"""

    async def test_rag_search_with_conversation_history(self, therapist_client):
        mock_results = {
            "query": "tell me more",
            "results": [
                {
                    "content": "Patient mentioned feeling better.",
                    "score": 0.88,
                    "source": "journal",
                    "metadata": {"patient_id": PATIENT_ID, "entry_date": "2025-06-15"},
                },
            ],
            "generated_answer": "Building on the previous discussion, the patient shows improvement.",
            "sources": ["journal:patient_001:2025-06-15"],
        }

        with patch("app.routers.search.search", new_callable=AsyncMock, return_value=mock_results) as mock_search:
            resp = await therapist_client.post("/search/rag", json={
                "query": "tell me more",
                "conversationHistory": [
                    {"role": "user", "content": "What anxiety themes appear?"},
                    {"role": "assistant", "content": "Several anxiety-related entries found."},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["generatedAnswer"] is not None
            # verify conversation history was passed to search
            call_kwargs = mock_search.call_args
            history = call_kwargs.kwargs.get("conversation_history", [])
            assert len(history) == 2
            assert history[0]["role"] == "user"

    async def test_rag_search_history_truncated(self, therapist_client):
        mock_results = {
            "query": "test",
            "results": [],
            "generated_answer": None,
            "sources": [],
        }

        # send more than 10 history items
        long_history = [
            {"role": "user", "content": f"msg {i}"} for i in range(15)
        ]

        with patch("app.routers.search.search", new_callable=AsyncMock, return_value=mock_results) as mock_search:
            resp = await therapist_client.post("/search/rag", json={
                "query": "test",
                "conversationHistory": long_history,
            })
            assert resp.status_code == 200
            # router truncates to 10
            call_kwargs = mock_search.call_args
            history = call_kwargs.kwargs.get("conversation_history", [])
            assert len(history) == 10


class TestClassifyThemes:
    """journal theme classification helper"""

    def test_anxiety_detected(self):
        themes = _classify_themes("I feel so anxious and worried about everything")
        assert "anxiety" in themes

    def test_depression_detected(self):
        themes = _classify_themes("Feeling depressed and hopeless today")
        assert "depression" in themes

    def test_positive_detected(self):
        themes = _classify_themes("I am so grateful and happy with my progress")
        assert "positive" in themes

    def test_multiple_themes(self):
        themes = _classify_themes("Anxious about work deadline but therapy helped with coping")
        assert "anxiety" in themes
        assert "work" in themes
        assert "therapy" in themes

    def test_unclassified_fallback(self):
        themes = _classify_themes("The weather is nice outside today")
        assert themes == ["unclassified"]

    def test_sleep_detected(self):
        themes = _classify_themes("My insomnia is getting worse, I can't sleep")
        assert "sleep" in themes
