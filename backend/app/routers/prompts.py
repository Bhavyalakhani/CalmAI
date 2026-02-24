# prompts router — therapist-assigned reflection prompts for patients
# therapists create prompts, patients view pending ones, journal submission links responses

import logging
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from bson import ObjectId

from app.models.prompt import PromptCreate, PromptResponse
from app.services.db import Database, get_db
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["prompts"])


def _doc_to_prompt(doc: dict, therapist_name: str = "") -> PromptResponse:
    """convert a mongodb prompt document to response model"""
    return PromptResponse(
        promptId=doc.get("prompt_id", str(doc.get("_id", ""))),
        therapistId=doc.get("therapist_id", ""),
        therapistName=therapist_name or doc.get("therapist_name", ""),
        patientId=doc.get("patient_id", ""),
        promptText=doc.get("prompt_text", ""),
        createdAt=doc.get("created_at", ""),
        status=doc.get("status", "pending"),
        responseJournalId=doc.get("response_journal_id"),
        responseContent=doc.get("response_content"),
        respondedAt=doc.get("responded_at"),
    )


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    body: PromptCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """therapist creates a reflection prompt for a patient"""

    if current_user.get("role") != "therapist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only therapists can create prompts",
        )

    # verify therapist owns this patient
    if body.patient_id not in current_user.get("patient_ids", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this patient",
        )

    now = datetime.now(timezone.utc)
    raw = f"{current_user['id']}:{body.patient_id}:{now.isoformat()}"
    prompt_id = hashlib.md5(raw.encode()).hexdigest()[:12]

    doc = {
        "prompt_id": prompt_id,
        "therapist_id": current_user["id"],
        "therapist_name": current_user.get("name", ""),
        "patient_id": body.patient_id,
        "prompt_text": body.prompt_text,
        "created_at": now.isoformat(),
        "status": "pending",
        "response_journal_id": None,
        "response_content": None,
        "responded_at": None,
    }

    await db.prompts.insert_one(doc)
    logger.info(f"Prompt created: {prompt_id} for patient {body.patient_id}")

    return _doc_to_prompt(doc, therapist_name=current_user.get("name", ""))


@router.get("/{patient_id}", response_model=list[PromptResponse])
async def get_patient_prompts(
    patient_id: str,
    prompt_status: str = Query(None, alias="status", description="filter by status: pending or responded"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """get prompts for a patient.
    patients see their own prompts, therapists see their patients' prompts."""

    # patients can only see their own
    if current_user.get("role") == "patient":
        if patient_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own prompts",
            )
    elif current_user.get("role") == "therapist":
        if patient_id not in current_user.get("patient_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this patient",
            )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    query: dict = {"patient_id": patient_id}
    if prompt_status in ("pending", "responded"):
        query["status"] = prompt_status

    cursor = db.prompts.find(query).sort("created_at", -1)
    prompts = []
    async for doc in cursor:
        prompts.append(_doc_to_prompt(doc))

    return prompts


@router.get("/{patient_id}/all", response_model=list[PromptResponse])
async def get_all_prompts_for_patient(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """therapist gets all prompts (pending + responded) with linked journal content"""

    if current_user.get("role") != "therapist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only therapists can view all prompts",
        )

    if patient_id not in current_user.get("patient_ids", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this patient",
        )

    cursor = db.prompts.find({"patient_id": patient_id}).sort("created_at", -1)
    prompts = []
    async for doc in cursor:
        # if responded, fetch the linked journal content
        if doc.get("status") == "responded" and doc.get("response_journal_id"):
            journal = await db.journals.find_one({"journal_id": doc["response_journal_id"]})
            if journal:
                doc["response_content"] = journal.get("content", "")
        prompts.append(_doc_to_prompt(doc))

    return prompts


@router.patch("/{prompt_id}/respond", response_model=PromptResponse)
async def respond_to_prompt(
    prompt_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """internal: mark a prompt as responded and link a journal id.
    typically called by the journal submission endpoint, not directly by users."""

    # this is a restricted internal route — only the system should call it
    # but we allow patient access for the link flow
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Use journal submission with promptId to respond to prompts",
    )
