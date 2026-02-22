# conversation models — response schemas for conversation data
# mirrors frontend types/index.ts Conversation

from typing import Optional
from pydantic import BaseModel, Field


class ConversationResponse(BaseModel):
    """conversation record from the conversations collection"""
    id: str
    context: str = ""
    response: str = ""
    topic: Optional[str] = None
    severity: Optional[str] = None
    context_word_count: int = Field(0, alias="contextWordCount")
    response_word_count: int = Field(0, alias="responseWordCount")
    source_file: str = Field("", alias="sourceFile")

    model_config = {"populate_by_name": True}


class ConversationListResponse(BaseModel):
    """paginated list of conversations"""
    conversations: list[ConversationResponse]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")

    model_config = {"populate_by_name": True}
