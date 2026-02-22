# search router — rag assistant endpoint
# therapist-only: queries patient data using vector search + gemini

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.rag import RAGQuery, RAGResponse, RAGResult
from app.services.db import Database, get_db
from app.services.rag_service import search
from app.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


async def _resolve_pipeline_id(user_id: str, db: Database) -> str:
    """resolve a mongodb objectid to pipeline patient_id (e.g. 'patient_001')"""
    from bson import ObjectId
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"pipeline_patient_id": 1})
        if user and user.get("pipeline_patient_id"):
            return user["pipeline_patient_id"]
    except Exception:
        pass
    return user_id


@router.post("/rag", response_model=RAGResponse)
async def rag_search(
    body: RAGQuery,
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """perform rag assistant query across journals and conversations.

    retrieves semantically similar documents from the vector store,
    then generates an answer using gemini with source citations.
    supports follow-up questions via conversation history.
    """

    # if patient_id is specified, verify therapist has access
    patient_id = body.patient_id
    if patient_id:
        if patient_id not in current_user.get("patient_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this patient's data",
            )
        # resolve to pipeline patient_id for rag_vectors collection
        patient_id = await _resolve_pipeline_id(patient_id, db)

    # truncate conversation history to prevent abuse
    history = [msg.model_dump() for msg in body.conversation_history[:10]]

    result = await search(
        db=db,
        query=body.query,
        top_k=body.top_k,
        patient_id=patient_id,
        source_type=body.source_type,
        conversation_history=history,
    )

    return RAGResponse(
        query=result["query"],
        results=[RAGResult(**r) for r in result["results"]],
        generatedAnswer=result.get("generated_answer"),
        sources=result.get("sources", []),
    )
