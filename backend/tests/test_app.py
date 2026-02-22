# tests for the health check and app configuration
# basic app-level tests

import pytest


class TestHealthCheck:
    """app health and config"""

    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "calmai-api"

    async def test_openapi_schema(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "CalmAI API"

    async def test_docs_available(self, client):
        resp = await client.get("/docs")
        assert resp.status_code == 200
