# analytics models — patient analytics response schemas
# mirrors frontend types/index.ts PatientAnalytics, TopicDistribution, etc.
# supports both new bertopic topic_distribution format and legacy theme_distribution

from typing import Optional
from pydantic import BaseModel, Field


class TopicDistribution(BaseModel):
    """a single topic from bertopic model output"""
    topic_id: int = Field(..., alias="topicId")
    label: str
    keywords: list[str] = Field(default_factory=list)
    percentage: float
    count: int

    model_config = {"populate_by_name": True}


class TopicOverTime(BaseModel):
    """topic frequency for a given month"""
    month: str
    topic_id: int = Field(..., alias="topicId")
    label: str
    frequency: int

    model_config = {"populate_by_name": True}


class RepresentativeEntry(BaseModel):
    """a journal entry that best represents a topic"""
    topic_id: int = Field(..., alias="topicId")
    label: str
    journal_id: str = Field("", alias="journalId")
    content: str = ""
    entry_date: str = Field("", alias="entryDate")
    probability: float = 0.0

    model_config = {"populate_by_name": True}


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
    topic_distribution: list[TopicDistribution] = Field(default_factory=list, alias="topicDistribution")
    topics_over_time: list[TopicOverTime] = Field(default_factory=list, alias="topicsOverTime")
    representative_entries: list[RepresentativeEntry] = Field(default_factory=list, alias="representativeEntries")
    model_version: str = Field("", alias="modelVersion")
    avg_word_count: float = Field(0.0, alias="avgWordCount")
    entry_frequency: list[EntryFrequency] = Field(default_factory=list, alias="entryFrequency")
    date_range: Optional[DateRange] = Field(None, alias="dateRange")
    computed_at: str = Field("", alias="computedAt")

    model_config = {"populate_by_name": True}
