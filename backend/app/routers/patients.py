# patients router — list, retrieve, and invite patients for a therapist
# therapist-only endpoints, reads from users and invite_codes collections

import logging
import secrets
import string
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from bson import ObjectId

from app.models.user import PatientResponse
from app.models.analytics import PatientAnalyticsResponse
from app.models.invite import InviteCodeResponse, InviteCodeCreate
from app.services.db import Database, get_db
from app.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])

# invite code config
INVITE_CODE_LENGTH = 8
INVITE_CODE_EXPIRY_DAYS = 7


def _generate_code() -> str:
    """generate a random uppercase alphanumeric invite code"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


@router.get("", response_model=list[PatientResponse])
async def list_patients(
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """list all patients linked to the authenticated therapist"""
    patient_ids = current_user.get("patient_ids", [])

    if not patient_ids:
        return []

    # convert string ids to objectid for query
    object_ids = []
    for pid in patient_ids:
        try:
            object_ids.append(ObjectId(pid))
        except Exception:
            continue

    cursor = db.users.find({"_id": {"$in": object_ids}, "role": "patient"})
    patients = []
    async for doc in cursor:
        patients.append(PatientResponse(
            id=str(doc["_id"]),
            email=doc.get("email", ""),
            name=doc.get("name", ""),
            role="patient",
            avatarUrl=doc.get("avatar_url"),
            createdAt=doc.get("created_at", ""),
            therapistId=doc.get("therapist_id", ""),
            dateOfBirth=doc.get("date_of_birth"),
            onboardedAt=doc.get("onboarded_at", doc.get("created_at", "")),
        ))

    return patients


@router.post("/invite", response_model=InviteCodeCreate, status_code=status.HTTP_201_CREATED)
async def generate_invite_code(
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """generate a new single-use invite code for patient onboarding"""
    therapist_id = current_user.get("id", "")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=INVITE_CODE_EXPIRY_DAYS)

    # generate a unique code (retry on collision)
    for _ in range(10):
        code = _generate_code()
        existing = await db.invite_codes.find_one({"code": code})
        if not existing:
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique invite code",
        )

    invite_doc = {
        "code": code,
        "therapist_id": therapist_id,
        "therapist_name": current_user.get("name", ""),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "is_used": False,
        "used_by": None,
    }

    await db.invite_codes.insert_one(invite_doc)
    logger.info(f"Invite code generated: {code} by therapist {therapist_id}")

    return InviteCodeCreate(
        code=code,
        expiresAt=expires_at.isoformat(),
    )


@router.get("/invites", response_model=list[InviteCodeResponse])
async def list_invite_codes(
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """list all invite codes created by this therapist"""
    therapist_id = current_user.get("id", "")

    cursor = db.invite_codes.find({"therapist_id": therapist_id})
    codes = []
    async for doc in cursor:
        codes.append(InviteCodeResponse(
            code=doc.get("code", ""),
            therapistId=doc.get("therapist_id", ""),
            therapistName=doc.get("therapist_name", ""),
            createdAt=doc.get("created_at", ""),
            expiresAt=doc.get("expires_at", ""),
            isUsed=doc.get("is_used", False),
            usedBy=doc.get("used_by"),
        ))

    return codes


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """get a specific patient by id (therapist must own the patient)"""
    # verify therapist owns this patient
    if patient_id not in current_user.get("patient_ids", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this patient",
        )

    try:
        doc = await db.users.find_one({"_id": ObjectId(patient_id), "role": "patient"})
    except Exception:
        doc = None

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return PatientResponse(
        id=str(doc["_id"]),
        email=doc.get("email", ""),
        name=doc.get("name", ""),
        role="patient",
        avatarUrl=doc.get("avatar_url"),
        createdAt=doc.get("created_at", ""),
        therapistId=doc.get("therapist_id", ""),
        dateOfBirth=doc.get("date_of_birth"),
        onboardedAt=doc.get("onboarded_at", doc.get("created_at", "")),
    )
