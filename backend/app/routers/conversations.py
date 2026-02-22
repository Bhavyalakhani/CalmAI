# conversations router — list and search conversations
# therapist-only endpoints, reads from conversations collection

import logging
from fastapi import APIRouter, Depends, Query

from app.models.conversation import ConversationResponse, ConversationListResponse
from app.services.db import Database, get_db
from app.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


def _doc_to_conversation(doc: dict) -> ConversationResponse:
    """convert a mongodb conversation document to response model"""
    return ConversationResponse(
        id=doc.get("conversation_id", str(doc.get("_id", ""))),
        context=doc.get("context", ""),
        response=doc.get("response", ""),
        topic=doc.get("topic"),
        severity=doc.get("severity"),
        contextWordCount=doc.get("context_word_count", 0),
        responseWordCount=doc.get("response_word_count", 0),
        sourceFile=doc.get("source_file", ""),
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    topic: str = Query(None, description="filter by topic"),
    severity: str = Query(None, description="filter by severity level"),
    search: str = Query(None, description="text search in context/response"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """list conversations with optional topic/severity filters. therapist-only."""

    query = {}
    if topic:
        query["topic"] = topic
    if severity:
        query["severity"] = severity
    if search:
        query["$or"] = [
            {"context": {"$regex": search, "$options": "i"}},
            {"response": {"$regex": search, "$options": "i"}},
        ]

    total = await db.conversations.count_documents(query)
    skip = (page - 1) * page_size
    cursor = db.conversations.find(query).skip(skip).limit(page_size)

    conversations = []
    async for doc in cursor:
        conversations.append(_doc_to_conversation(doc))

    return ConversationListResponse(
        conversations=conversations,
        total=total,
        page=page,
        pageSize=page_size,
    )
