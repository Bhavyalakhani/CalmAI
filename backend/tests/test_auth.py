# tests for auth router — signup, login, me, refresh
# tests for app/routers/auth.py

import copy
import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from tests.conftest import (
    THERAPIST_DOC, PATIENT_DOC, THERAPIST_ID, PATIENT_ID,
    THERAPIST_OID, PATIENT_OID, MockDatabase,
)
from app.services.auth_service import hash_password, create_access_token, create_refresh_token
from app.services.db import get_db
from app.dependencies import get_current_user
from app.main import app


class TestSignup:
    """user registration endpoint"""

    async def test_signup_therapist_success(self, client, mock_db):
        # clear existing users so no email conflicts
        mock_db.users._data = []

        resp = await client.post("/auth/signup", json={
            "email": "new.therapist@calmai.com",
            "password": "securepass123",
            "name": "Dr. New Therapist",
            "role": "therapist",
            "specialization": "Trauma Therapy",
            "licenseNumber": "PSY-2025-99999",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert data["token_type"] == "bearer"

    async def test_signup_patient_success(self, client, mock_db):
        mock_db.users._data = [copy.deepcopy(THERAPIST_DOC)]

        # create an invite code for the patient to use
        from datetime import datetime, timezone, timedelta
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        mock_db.invite_codes._data = [{
            "code": "TEST1234",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires,
            "is_used": False,
            "used_by": None,
        }]

        resp = await client.post("/auth/signup", json={
            "email": "new.patient@email.com",
            "password": "securepass123",
            "name": "New Patient",
            "role": "patient",
            "therapistId": "TEST1234",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "accessToken" in data

        # verify invite code was marked as used
        code_doc = mock_db.invite_codes._data[0]
        assert code_doc["is_used"] is True
        assert code_doc["used_by"] is not None

    async def test_signup_patient_missing_invite_code(self, client, mock_db):
        mock_db.users._data = []

        resp = await client.post("/auth/signup", json={
            "email": "no.code@email.com",
            "password": "securepass123",
            "name": "No Code Patient",
            "role": "patient",
        })
        assert resp.status_code == 422
        assert "Invite code is required" in resp.json()["detail"]

    async def test_signup_patient_invalid_invite_code(self, client, mock_db):
        mock_db.users._data = []
        mock_db.invite_codes._data = []

        resp = await client.post("/auth/signup", json={
            "email": "bad.code@email.com",
            "password": "securepass123",
            "name": "Bad Code Patient",
            "role": "patient",
            "therapistId": "INVALID9",
        })
        assert resp.status_code == 404
        assert "Invalid invite code" in resp.json()["detail"]

    async def test_signup_patient_used_invite_code(self, client, mock_db):
        mock_db.users._data = []
        from datetime import datetime, timezone, timedelta
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        mock_db.invite_codes._data = [{
            "code": "USED1234",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires,
            "is_used": True,
            "used_by": "someone",
        }]

        resp = await client.post("/auth/signup", json={
            "email": "used.code@email.com",
            "password": "securepass123",
            "name": "Used Code Patient",
            "role": "patient",
            "therapistId": "USED1234",
        })
        assert resp.status_code == 410
        assert "already been used" in resp.json()["detail"]

    async def test_signup_patient_expired_invite_code(self, client, mock_db):
        mock_db.users._data = []
        from datetime import datetime, timezone, timedelta
        expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mock_db.invite_codes._data = [{
            "code": "EXPD1234",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expired,
            "is_used": False,
            "used_by": None,
        }]

        resp = await client.post("/auth/signup", json={
            "email": "expired.code@email.com",
            "password": "securepass123",
            "name": "Expired Code Patient",
            "role": "patient",
            "therapistId": "EXPD1234",
        })
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"]

    async def test_signup_duplicate_email(self, client):
        resp = await client.post("/auth/signup", json={
            "email": "dr.chen@calmai.com",
            "password": "securepass123",
            "name": "Duplicate",
            "role": "therapist",
            "specialization": "CBT",
            "licenseNumber": "PSY-0000",
        })
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_signup_therapist_missing_license(self, client, mock_db):
        mock_db.users._data = []

        resp = await client.post("/auth/signup", json={
            "email": "no.license@calmai.com",
            "password": "securepass123",
            "name": "Dr. No License",
            "role": "therapist",
            "specialization": "CBT",
        })
        assert resp.status_code == 422

    async def test_signup_therapist_missing_specialization(self, client, mock_db):
        mock_db.users._data = []

        resp = await client.post("/auth/signup", json={
            "email": "no.spec@calmai.com",
            "password": "securepass123",
            "name": "Dr. No Spec",
            "role": "therapist",
            "licenseNumber": "PSY-0001",
        })
        assert resp.status_code == 422

    async def test_signup_short_password(self, client, mock_db):
        resp = await client.post("/auth/signup", json={
            "email": "fail@email.com",
            "password": "short",
            "name": "Test",
            "role": "patient",
        })
        assert resp.status_code == 422


class TestLogin:
    """login endpoint"""

    async def test_login_success(self, client):
        resp = await client.post("/auth/login", json={
            "email": "dr.chen@calmai.com",
            "password": "calmai123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data

    async def test_login_wrong_password(self, client):
        resp = await client.post("/auth/login", json={
            "email": "dr.chen@calmai.com",
            "password": "wrong_password",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client):
        resp = await client.post("/auth/login", json={
            "email": "nobody@calmai.com",
            "password": "calmai123",
        })
        assert resp.status_code == 401


class TestMe:
    """get current user profile"""

    async def test_get_me_therapist(self, therapist_client):
        resp = await therapist_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Sarah Chen"
        assert data["role"] == "therapist"
        assert "specialization" in data

    async def test_get_me_patient(self, patient_client):
        resp = await patient_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Alex Rivera"
        assert data["role"] == "patient"

    async def test_get_me_no_auth(self, client):
        # clear any auth overrides
        app.dependency_overrides.pop(get_current_user, None)
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)


class TestRefresh:
    """token refresh endpoint"""

    async def test_refresh_success(self, client):
        refresh = create_refresh_token({"sub": THERAPIST_ID, "role": "therapist"})
        resp = await client.post("/auth/refresh", json={
            "refreshToken": refresh,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "accessToken" in data
        assert "refreshToken" in data

    async def test_refresh_invalid_token(self, client):
        resp = await client.post("/auth/refresh", json={
            "refreshToken": "invalid.token.here",
        })
        assert resp.status_code == 401

    async def test_refresh_with_access_token_fails(self, client):
        # access tokens should not work for refresh
        access = create_access_token({"sub": THERAPIST_ID, "role": "therapist"})
        resp = await client.post("/auth/refresh", json={
            "refreshToken": access,
        })
        assert resp.status_code == 401


class TestUpdateProfile:
    """profile update endpoint"""

    async def test_update_name(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/profile", json={
            "name": "Dr. Sarah Chen-Updated",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Sarah Chen-Updated"

    async def test_update_specialization(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/profile", json={
            "specialization": "Trauma Therapy",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["specialization"] == "Trauma Therapy"

    async def test_update_practice_name(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/profile", json={
            "practiceName": "New Practice Name",
        })
        assert resp.status_code == 200

    async def test_update_multiple_fields(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/profile", json={
            "name": "Dr. Updated",
            "specialization": "DBT",
            "practiceName": "Updated Practice",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Updated"

    async def test_update_empty_body(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/profile", json={})
        assert resp.status_code == 422
        assert "No fields to update" in resp.json()["detail"]

    async def test_patient_cannot_update_specialization(self, patient_client, mock_db):
        resp = await patient_client.patch("/auth/profile", json={
            "name": "Updated Patient",
            "specialization": "Ignored Field",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Patient"
        # specialization is therapist-only, should be ignored for patients
        assert "specialization" not in data or data.get("specialization") is None


class TestUpdateNotifications:
    """notification preferences endpoint"""

    async def test_save_notifications(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/notifications", json={
            "emailNotifications": True,
            "journalAlerts": False,
            "weeklyDigest": True,
        })
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_save_notifications_defaults(self, therapist_client, mock_db):
        resp = await therapist_client.patch("/auth/notifications", json={})
        assert resp.status_code == 200


class TestDeleteAccount:
    """account deletion endpoint"""

    async def test_delete_therapist_account(self, therapist_client, mock_db):
        initial_count = len(mock_db.users._data)
        resp = await therapist_client.delete("/auth/account")
        assert resp.status_code == 204
        assert len(mock_db.users._data) == initial_count - 1

    async def test_delete_patient_account(self, patient_client, mock_db):
        initial_count = len(mock_db.users._data)
        resp = await patient_client.delete("/auth/account")
        assert resp.status_code == 204
        assert len(mock_db.users._data) == initial_count - 1

    async def test_delete_patient_unlinks_from_therapist(self, patient_client, mock_db):
        # verify patient is in therapist's patient_ids before deletion
        therapist = mock_db.users._data[0]
        assert PATIENT_ID in therapist.get("patient_ids", [])

        resp = await patient_client.delete("/auth/account")
        assert resp.status_code == 204

        # verify patient was removed from therapist's list
        therapist = mock_db.users._data[0]
        assert PATIENT_ID not in therapist.get("patient_ids", [])


class TestAuthGuards:
    """no-auth guard tests for new endpoints"""

    async def test_update_profile_no_auth(self, client):
        app.dependency_overrides.pop(get_current_user, None)
        resp = await client.patch("/auth/profile", json={"name": "Anon"})
        assert resp.status_code in (401, 403)

    async def test_update_notifications_no_auth(self, client):
        app.dependency_overrides.pop(get_current_user, None)
        resp = await client.patch("/auth/notifications", json={})
        assert resp.status_code in (401, 403)

    async def test_delete_account_no_auth(self, client):
        app.dependency_overrides.pop(get_current_user, None)
        resp = await client.delete("/auth/account")
        assert resp.status_code in (401, 403)


class TestDeleteTherapistUnlinks:
    """therapist deletion unlinks all patients"""

    async def test_delete_therapist_unlinks_patients(self, therapist_client, mock_db):
        # before deletion, patients reference this therapist
        assert mock_db.users._data[1].get("therapist_id") == THERAPIST_ID

        resp = await therapist_client.delete("/auth/account")
        assert resp.status_code == 204

        # remaining patients should have therapist_id cleared
        remaining = [d for d in mock_db.users._data if d.get("role") == "patient"]
        for p in remaining:
            assert p.get("therapist_id") == ""


class TestProfilePatient:
    """patient-specific profile and notification tests"""

    async def test_patient_update_name(self, patient_client, mock_db):
        resp = await patient_client.patch("/auth/profile", json={
            "name": "Alex Updated",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Alex Updated"
        assert data["role"] == "patient"

    async def test_patient_save_notifications(self, patient_client, mock_db):
        resp = await patient_client.patch("/auth/notifications", json={
            "emailNotifications": False,
            "journalAlerts": True,
            "weeklyDigest": False,
        })
        assert resp.status_code == 200
        assert "message" in resp.json()
