# user models — auth, therapist, and patient schemas
# mirrors frontend types/index.ts User, Therapist, Patient

from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


# auth

class UserCreate(BaseModel):
    email: str = Field(..., description="user email address")
    password: str = Field(..., min_length=8, description="plaintext password (min 8 chars)")
    name: str = Field(..., min_length=1, description="full name")
    role: Literal["therapist", "patient"] = Field(..., description="user role")

    # therapist-specific fields
    specialization: Optional[str] = None
    license_number: Optional[str] = Field(None, alias="licenseNumber")
    practice_name: Optional[str] = Field(None, alias="practiceName")

    # patient-specific fields
    therapist_id: Optional[str] = Field(None, alias="therapistId")
    date_of_birth: Optional[str] = Field(None, alias="dateOfBirth")

    model_config = {"populate_by_name": True}


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = "bearer"

    model_config = {"populate_by_name": True}


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., alias="refreshToken")

    model_config = {"populate_by_name": True}


# user responses

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: Literal["therapist", "patient"]
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


class TherapistResponse(UserResponse):
    role: Literal["therapist"] = "therapist"
    specialization: str = ""
    license_number: str = Field("", alias="licenseNumber")
    practice_name: Optional[str] = Field(None, alias="practiceName")
    patient_ids: list[str] = Field(default_factory=list, alias="patientIds")

    model_config = {"populate_by_name": True}


class PatientResponse(UserResponse):
    role: Literal["patient"] = "patient"
    therapist_id: str = Field("", alias="therapistId")
    date_of_birth: Optional[str] = Field(None, alias="dateOfBirth")
    onboarded_at: str = Field("", alias="onboardedAt")
    therapist_name: Optional[str] = Field(None, alias="therapistName")
    therapist_specialization: Optional[str] = Field(None, alias="therapistSpecialization")
    therapist_license_number: Optional[str] = Field(None, alias="therapistLicenseNumber")

    model_config = {"populate_by_name": True}


# profile update

class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="full name")
    specialization: Optional[str] = None
    practice_name: Optional[str] = Field(None, alias="practiceName")

    model_config = {"populate_by_name": True}


# notification preferences

class NotificationPreferences(BaseModel):
    email_notifications: bool = Field(True, alias="emailNotifications")
    journal_alerts: bool = Field(True, alias="journalAlerts")
    weekly_digest: bool = Field(True, alias="weeklyDigest")

    model_config = {"populate_by_name": True}


# password change

class PasswordChange(BaseModel):
    current_password: str = Field(..., alias="currentPassword", min_length=1)
    new_password: str = Field(..., alias="newPassword", min_length=8)

    model_config = {"populate_by_name": True}
