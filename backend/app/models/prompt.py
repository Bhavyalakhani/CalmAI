# prompt models — therapist prompts and patient responses
# therapists assign reflection prompts, patients respond via journal entries

from typing import Optional, Literal
from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    """payload for therapist to create a prompt for a patient"""
    patient_id: str = Field(..., alias="patientId", description="target patient id")
    prompt_text: str = Field(..., alias="promptText", min_length=5, max_length=2000, description="prompt/question text")

    model_config = {"populate_by_name": True}


class PromptResponse(BaseModel):
    """full prompt document returned to frontend"""
    prompt_id: str = Field(..., alias="promptId")
    therapist_id: str = Field(..., alias="therapistId")
    therapist_name: str = Field("", alias="therapistName")
    patient_id: str = Field(..., alias="patientId")
    prompt_text: str = Field(..., alias="promptText")
    created_at: str = Field(..., alias="createdAt")
    status: Literal["pending", "responded"] = "pending"
    response_journal_id: Optional[str] = Field(None, alias="responseJournalId")
    response_content: Optional[str] = Field(None, alias="responseContent")
    responded_at: Optional[str] = Field(None, alias="respondedAt")

    model_config = {"populate_by_name": True}
