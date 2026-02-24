# tests for patients router — list, get, invite code, and remove endpoints
# therapist-only endpoints

import pytest
from bson import ObjectId
from tests.conftest import PATIENT_ID, PATIENT_2_ID, THERAPIST_ID


class TestListPatients:
    """list patients for a therapist"""

    async def test_list_patients_success(self, therapist_client):
        resp = await therapist_client.get("/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        names = [p["name"] for p in data]
        assert "Alex Rivera" in names
        assert "Jordan Kim" in names

    async def test_list_patients_has_required_fields(self, therapist_client):
        resp = await therapist_client.get("/patients")
        data = resp.json()
        for patient in data:
            assert "id" in patient
            assert "email" in patient
            assert "name" in patient
            assert "role" in patient
            assert patient["role"] == "patient"

    async def test_patient_cannot_list_patients(self, patient_client):
        resp = await patient_client.get("/patients")
        assert resp.status_code == 403


class TestGetPatient:
    """get a specific patient"""

    async def test_get_patient_success(self, therapist_client):
        resp = await therapist_client.get(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Alex Rivera"
        assert data["id"] == PATIENT_ID

    async def test_get_patient_not_owned(self, therapist_client, mock_db):
        # use a random id not in therapist's patient_ids
        fake_id = "507f1f77bcf86cd799439011"
        resp = await therapist_client.get(f"/patients/{fake_id}")
        assert resp.status_code == 403

    async def test_get_patient_not_found(self, therapist_client, mock_db):
        # add a valid patient_id to therapist but no matching doc in db
        fake_oid = "507f1f77bcf86cd799439011"
        for doc in mock_db.users._data:
            if doc.get("role") == "therapist":
                doc["patient_ids"].append(fake_oid)
                break

        resp = await therapist_client.get(f"/patients/{fake_oid}")
        assert resp.status_code == 404

    async def test_patient_cannot_get_patients(self, patient_client):
        resp = await patient_client.get(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 403


class TestGenerateInviteCode:
    """generate invite codes for patient onboarding"""

    async def test_generate_invite_code_success(self, therapist_client):
        resp = await therapist_client.post("/patients/invite")
        assert resp.status_code == 201
        data = resp.json()
        assert "code" in data
        assert len(data["code"]) == 8
        assert "expiresAt" in data
        assert "message" in data

    async def test_generate_invite_code_is_alphanumeric(self, therapist_client):
        resp = await therapist_client.post("/patients/invite")
        data = resp.json()
        assert data["code"].isalnum()
        assert data["code"] == data["code"].upper()

    async def test_patient_cannot_generate_invite(self, patient_client):
        resp = await patient_client.post("/patients/invite")
        assert resp.status_code == 403

    async def test_generate_multiple_unique_codes(self, therapist_client):
        codes = set()
        for _ in range(5):
            resp = await therapist_client.post("/patients/invite")
            assert resp.status_code == 201
            codes.add(resp.json()["code"])
        # all codes should be unique
        assert len(codes) == 5


class TestListInviteCodes:
    """list invite codes for the current therapist"""

    async def test_list_invite_codes_empty(self, therapist_client):
        resp = await therapist_client.get("/patients/invites")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_invite_codes_after_generation(self, therapist_client, mock_db):
        # generate a code first
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        mock_db.invite_codes._data = [{
            "code": "ABCD1234",
            "therapist_id": THERAPIST_ID,
            "therapist_name": "Dr. Sarah Chen",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "is_used": False,
            "used_by": None,
        }]

        resp = await therapist_client.get("/patients/invites")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "ABCD1234"
        assert data[0]["isUsed"] is False

    async def test_list_shows_used_status(self, therapist_client, mock_db):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        mock_db.invite_codes._data = [
            {
                "code": "USED0001",
                "therapist_id": THERAPIST_ID,
                "therapist_name": "Dr. Sarah Chen",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=7)).isoformat(),
                "is_used": True,
                "used_by": "patient-123",
            },
            {
                "code": "ACTV0001",
                "therapist_id": THERAPIST_ID,
                "therapist_name": "Dr. Sarah Chen",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=7)).isoformat(),
                "is_used": False,
                "used_by": None,
            },
        ]

        resp = await therapist_client.get("/patients/invites")
        data = resp.json()
        assert len(data) == 2
        used = [c for c in data if c["isUsed"]]
        active = [c for c in data if not c["isUsed"]]
        assert len(used) == 1
        assert len(active) == 1

    async def test_patient_cannot_list_invites(self, patient_client):
        resp = await patient_client.get("/patients/invites")
        assert resp.status_code == 403


class TestRemovePatient:
    """therapist removes a patient and all their data"""

    async def test_remove_patient_success(self, therapist_client, mock_db):
        # seed some patient data
        mock_db.journals._data.append({
            "_id": ObjectId(), "journal_id": "j999", "patient_id": PATIENT_ID,
            "content": "test", "entry_date": "2025-06-10",
        })
        mock_db.rag_vectors._data.append({
            "_id": ObjectId(), "patient_id": PATIENT_ID, "content": "vec",
        })
        mock_db.prompts._data.append({
            "_id": ObjectId(), "patient_id": PATIENT_ID, "text": "prompt",
        })

        users_before = len(mock_db.users._data)
        resp = await therapist_client.delete(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 204

        # patient user doc removed
        assert len(mock_db.users._data) == users_before - 1
        remaining_ids = [str(d["_id"]) for d in mock_db.users._data]
        assert PATIENT_ID not in remaining_ids

    async def test_remove_patient_unlinks_from_therapist(self, therapist_client, mock_db):
        therapist = mock_db.users._data[0]
        assert PATIENT_ID in therapist.get("patient_ids", [])

        resp = await therapist_client.delete(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 204

        therapist = mock_db.users._data[0]
        assert PATIENT_ID not in therapist.get("patient_ids", [])

    async def test_remove_patient_deletes_journals(self, therapist_client, mock_db):
        # journals collection already has 2 journals for PATIENT_ID in conftest
        assert len(mock_db.journals._data) >= 1

        resp = await therapist_client.delete(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 204

        # all journals for this patient should be gone
        patient_journals = [j for j in mock_db.journals._data if j.get("patient_id") == PATIENT_ID]
        assert len(patient_journals) == 0

    async def test_remove_patient_deletes_analytics(self, therapist_client, mock_db):
        assert len(mock_db.patient_analytics._data) == 1

        resp = await therapist_client.delete(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 204

        assert len(mock_db.patient_analytics._data) == 0

    async def test_remove_patient_not_found(self, therapist_client, mock_db):
        fake_id = "507f1f77bcf86cd799439011"
        # add to therapist's patient_ids so it passes the ownership check attempt
        resp = await therapist_client.delete(f"/patients/{fake_id}")
        assert resp.status_code == 404

    async def test_remove_patient_not_owned(self, therapist_client, mock_db):
        # create a patient belonging to a different therapist
        other_patient_oid = ObjectId()
        mock_db.users._data.append({
            "_id": other_patient_oid,
            "email": "other@test.com",
            "name": "Other Patient",
            "role": "patient",
            "therapist_id": "some_other_therapist_id",
        })

        resp = await therapist_client.delete(f"/patients/{str(other_patient_oid)}")
        assert resp.status_code == 403

    async def test_patient_cannot_remove_patient(self, patient_client):
        resp = await patient_client.delete(f"/patients/{PATIENT_ID}")
        assert resp.status_code == 403
