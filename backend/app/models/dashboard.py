# dashboard models — stats and trend view models
# mirrors frontend types/index.ts DashboardStats, TrendDataPoint

from typing import Optional
from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    """aggregate stats for the therapist dashboard overview"""
    total_patients: int = Field(0, alias="totalPatients")
    total_journals: int = Field(0, alias="totalJournals")
    total_conversations: int = Field(0, alias="totalConversations")
    avg_entries_per_patient: float = Field(0.0, alias="avgEntriesPerPatient")
    active_patients: int = Field(0, alias="activePatients")

    model_config = {"populate_by_name": True}


class TrendDataPoint(BaseModel):
    """single data point in a mood/activity trend"""
    date: str
    value: float
    label: Optional[str] = None
