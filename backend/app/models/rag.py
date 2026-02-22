# rag models — search query and response schemas
# mirrors frontend types/index.ts RAGQuery, RAGResult, RAGResponse

from typing import Optional
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """single message in a conversation history turn"""
    role: str = Field(..., description="message role: user or assistant")
    content: str = Field(..., description="message content")


class RAGQuery(BaseModel):
    """search query for the rag assistant endpoint"""
    query: str = Field(..., min_length=1, description="natural language query")
    patient_id: Optional[str] = Field(None, alias="patientId", description="optional patient filter")
    top_k: int = Field(5, alias="topK", ge=1, le=20, description="number of results to return")
    source_type: Optional[str] = Field(None, alias="sourceType", description="filter: journal | conversation | None for all")
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        alias="conversationHistory",
        description="previous turns for follow-up context (max 10 turns)",
    )

    model_config = {"populate_by_name": True}


class RAGResult(BaseModel):
    """single search result from vector store"""
    content: str
    score: float
    source: str  # "conversation" or "journal"
    metadata: dict[str, str] = Field(default_factory=dict)


class RAGResponse(BaseModel):
    """full rag search response with generated answer and sources"""
    query: str
    results: list[RAGResult]
    generated_answer: Optional[str] = Field(None, alias="generatedAnswer")
    sources: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
