# journal models — entry creation and response schemas
# mirrors frontend types/index.ts JournalEntry

from typing import Optional
from pydantic import BaseModel, Field


class JournalCreate(BaseModel):
    """payload for patient journal submission — written to incoming_journals"""
    content: str = Field(..., min_length=10, max_length=10000, description="journal entry text")
    mood: Optional[int] = Field(None, ge=1, le=5, description="mood score 1-5")
    prompt_id: Optional[str] = Field(None, alias="promptId", description="prompt id if responding to a therapist prompt")

    model_config = {"populate_by_name": True}


class JournalEntryResponse(BaseModel):
    """full journal entry from the journals collection"""
    id: str
    patient_id: str = Field(..., alias="patientId")
    content: str
    entry_date: str = Field(..., alias="entryDate")
    themes: list[str] = Field(default_factory=list)
    word_count: int = Field(0, alias="wordCount")
    char_count: int = Field(0, alias="charCount")
    sentence_count: int = Field(0, alias="sentenceCount")
    avg_word_length: float = Field(0.0, alias="avgWordLength")
    mood: Optional[int] = None
    prompt_id: Optional[str] = Field(None, alias="promptId")
    day_of_week: Optional[str] = Field(None, alias="dayOfWeek")
    week_number: Optional[int] = Field(None, alias="weekNumber")
    month: Optional[int] = None
    year: Optional[int] = None
    days_since_last: Optional[int] = Field(None, alias="daysSinceLast")
    is_embedded: bool = Field(False, alias="isEmbedded")

    model_config = {"populate_by_name": True}


class JournalSubmitResponse(BaseModel):
    """response after journal submission to incoming_journals"""
    journal_id: str = Field(..., alias="journalId")
    message: str = "Journal entry submitted successfully. It will be processed by the pipeline."

    model_config = {"populate_by_name": True}
