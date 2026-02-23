# analytics router — patient analytics from the patient_analytics collection
# both therapists (for their patients) and patients (for themselves) can access
# supports new bertopic topic_distribution and legacy theme_distribution formats

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.analytics import (
    PatientAnalyticsResponse,
    TopicDistribution,
    TopicOverTime,
    RepresentativeEntry,
    EntryFrequency,
    DateRange,
)
from app.services.db import Database, get_db
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _resolve_pipeline_id(user_id: str, db: Database) -> str:
    """resolve a mongodb user objectid to the pipeline patient_id (e.g. 'patient_001').
    the data pipeline uses pipeline_patient_id, not objectids."""
    from bson import ObjectId
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"pipeline_patient_id": 1})
        if user and user.get("pipeline_patient_id"):
            return user["pipeline_patient_id"]
    except Exception:
        pass
    return user_id


def _clean_label(raw_label: str) -> str:
    """clean a topic label that may be stored as a stringified python list.
    bertopic 0.17.x multi-aspect representations store labels as lists like
    "['topic: Sleep Quality', '', '', ...]". this extracts the first non-empty
    element and strips the 'topic: ' prefix from the gemini prompt format.
    """
    import ast

    text = str(raw_label).strip()
    if not text:
        return ""

    # detect stringified list: "['topic: ...', '', '', ...]"
    if text.startswith("[") and text.endswith("]"):
        try:
            items = ast.literal_eval(text)
            if isinstance(items, list):
                for item in items:
                    s = str(item).strip() if item is not None else ""
                    if s:
                        text = s
                        break
                else:
                    return text  # no non-empty element, return raw
        except (ValueError, SyntaxError):
            pass  # not a valid python literal, treat as plain string

    # strip "topic: " prefix from gemini prompt format
    if text.lower().startswith("topic: "):
        text = text[7:].strip()
    elif text.lower().startswith("topic:"):
        text = text[6:].strip()

    # replace generic bertopic fallback labels like "Topic 24" with "Miscellaneous"
    if text and text.startswith("Topic ") and text.split(" ", 1)[1].strip().isdigit():
        text = "Miscellaneous"

    return text


def _doc_to_analytics(doc: dict) -> PatientAnalyticsResponse:
    """convert a mongodb patient_analytics document to response model.
    supports new bertopic format (topic_distribution as list of dicts with topic_id, label, keywords)
    and legacy format (theme_distribution as {theme: percentage} dict)."""

    total_entries = doc.get("total_entries", 0)
    topic_list: list[TopicDistribution] = []

    # new format: topic_distribution is a list of dicts
    raw_topics = doc.get("topic_distribution", [])
    if isinstance(raw_topics, list) and raw_topics:
        for item in raw_topics:
            if isinstance(item, dict):
                topic_list.append(TopicDistribution(
                    topicId=item.get("topic_id", -1),
                    label=_clean_label(item.get("label", "")),
                    keywords=item.get("keywords", []),
                    percentage=item.get("percentage", 0.0),
                    count=item.get("count", 0),
                ))
    else:
        # legacy fallback: theme_distribution as {theme: percentage} dict
        raw_themes = doc.get("theme_distribution", {})
        if isinstance(raw_themes, dict):
            for idx, (theme, value) in enumerate(sorted(raw_themes.items(), key=lambda x: x[1], reverse=True)):
                pct = float(value)
                count = round(pct / 100 * total_entries) if total_entries > 0 else 0
                topic_list.append(TopicDistribution(
                    topicId=idx, label=theme, keywords=[], percentage=pct, count=count,
                ))

    # topics over time
    topics_over_time: list[TopicOverTime] = []
    raw_tot = doc.get("topics_over_time", [])
    if isinstance(raw_tot, list):
        for item in raw_tot:
            if isinstance(item, dict):
                topics_over_time.append(TopicOverTime(
                    month=item.get("month", ""),
                    topicId=item.get("topic_id", -1),
                    label=_clean_label(item.get("label", "")),
                    frequency=item.get("frequency", 0),
                ))

    # representative entries
    representative_entries: list[RepresentativeEntry] = []
    raw_repr = doc.get("representative_entries", [])
    if isinstance(raw_repr, list):
        for item in raw_repr:
            if isinstance(item, dict):
                representative_entries.append(RepresentativeEntry(
                    topicId=item.get("topic_id", -1),
                    label=_clean_label(item.get("label", "")),
                    journalId=item.get("journal_id", ""),
                    content=item.get("content", ""),
                    entryDate=str(item.get("entry_date", "")),
                    probability=item.get("probability", 0.0),
                ))

    # parse entry_frequency
    raw_freq = doc.get("entry_frequency", {})
    freq_list = []
    if isinstance(raw_freq, dict):
        for month, count in sorted(raw_freq.items()):
            freq_list.append(EntryFrequency(month=month, count=count))
    elif isinstance(raw_freq, list):
        for item in raw_freq:
            if isinstance(item, dict):
                freq_list.append(EntryFrequency(month=item.get("month", ""), count=item.get("count", 0)))

    # parse date_range
    raw_date_range = doc.get("date_range")
    date_range = None
    if raw_date_range and isinstance(raw_date_range, dict):
        date_range = DateRange(
            first=str(raw_date_range.get("first", "")),
            last=str(raw_date_range.get("last", "")),
            spanDays=raw_date_range.get("span_days", 0),
        )

    return PatientAnalyticsResponse(
        patientId=doc.get("patient_id", ""),
        totalEntries=doc.get("total_entries", 0),
        topicDistribution=topic_list,
        topicsOverTime=topics_over_time,
        representativeEntries=representative_entries,
        modelVersion=doc.get("model_version", ""),
        avgWordCount=doc.get("avg_word_count", 0.0),
        entryFrequency=freq_list,
        dateRange=date_range,
        computedAt=doc.get("computed_at", ""),
    )


@router.get("/{patient_id}", response_model=PatientAnalyticsResponse)
async def get_patient_analytics(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """get analytics for a specific patient"""

    # access control: patients see own, therapists see their patients'
    if current_user["role"] == "patient":
        if patient_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own analytics",
            )
    elif current_user["role"] == "therapist":
        if patient_id not in current_user.get("patient_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this patient's analytics",
            )

    # resolve pipeline patient_id — pipeline data uses "patient_001" format,
    # but frontend passes mongodb objectid. try both.
    pipeline_id = await _resolve_pipeline_id(patient_id, db)

    doc = await db.patient_analytics.find_one({"patient_id": pipeline_id})
    if not doc:
        # fallback: try with the raw id as-is
        doc = await db.patient_analytics.find_one({"patient_id": patient_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics not found for this patient",
        )

    return _doc_to_analytics(doc)
