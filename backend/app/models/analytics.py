# analytics models — patient analytics response schemas
# mirrors frontend types/index.ts PatientAnalytics, ThemeDistribution, etc.

from typing import Optional
from pydantic import BaseModel, Field


class ThemeDistribution(BaseModel):
    theme: str
    percentage: float
    count: int


class EntryFrequency(BaseModel):
    month: str
    count: int


class DateRange(BaseModel):
    first: str
    last: str
    span_days: int = Field(..., alias="spanDays")

    model_config = {"populate_by_name": True}


class PatientAnalyticsResponse(BaseModel):
    """per-patient analytics from the patient_analytics collection"""
    patient_id: str = Field(..., alias="patientId")
    total_entries: int = Field(0, alias="totalEntries")
    theme_distribution: list[ThemeDistribution] = Field(default_factory=list, alias="themeDistribution")
    avg_word_count: float = Field(0.0, alias="avgWordCount")
    entry_frequency: list[EntryFrequency] = Field(default_factory=list, alias="entryFrequency")
    date_range: Optional[DateRange] = Field(None, alias="dateRange")
    computed_at: str = Field("", alias="computedAt")

    model_config = {"populate_by_name": True}
