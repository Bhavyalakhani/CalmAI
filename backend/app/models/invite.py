# invite code models — therapist-generated codes for patient onboarding
# codes are single-use, expire after 7 days

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class InviteCodeResponse(BaseModel):
    code: str = Field(..., description="unique 8-character invite code")
    therapist_id: str = Field(..., alias="therapistId")
    therapist_name: str = Field(..., alias="therapistName")
    created_at: str = Field(..., alias="createdAt")
    expires_at: str = Field(..., alias="expiresAt")
    is_used: bool = Field(False, alias="isUsed")
    used_by: Optional[str] = Field(None, alias="usedBy")

    model_config = {"populate_by_name": True}


class InviteCodeCreate(BaseModel):
    """response returned when a therapist generates a new invite code"""
    code: str
    expires_at: str = Field(..., alias="expiresAt")
    message: str = "Share this code with your patient to let them create an account"

    model_config = {"populate_by_name": True}
