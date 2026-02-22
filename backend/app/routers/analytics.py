# analytics router — patient analytics from the patient_analytics collection
# both therapists (for their patients) and patients (for themselves) can access

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.analytics import PatientAnalyticsResponse, ThemeDistribution, EntryFrequency, DateRange
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


def _doc_to_analytics(doc: dict) -> PatientAnalyticsResponse:
    """convert a mongodb patient_analytics document to response model"""

    # parse theme_distribution
    # pipeline stores {theme: percentage} (e.g. {"anxiety": 19.7, "work": 15.3})
    # we need to convert to ThemeDistribution objects with theme, percentage, count
    raw_themes = doc.get("theme_distribution", {})
    total_entries = doc.get("total_entries", 0)
    theme_list = []
    if isinstance(raw_themes, dict):
        for theme, value in sorted(raw_themes.items(), key=lambda x: x[1], reverse=True):
            pct = float(value)
            # approximate count from percentage and total entries
            count = round(pct / 100 * total_entries) if total_entries > 0 else 0
            theme_list.append(ThemeDistribution(theme=theme, percentage=pct, count=count))
    elif isinstance(raw_themes, list):
        for item in raw_themes:
            if isinstance(item, dict):
                theme_list.append(ThemeDistribution(
                    theme=item.get("theme", ""),
                    percentage=item.get("percentage", 0),
                    count=item.get("count", 0),
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
        themeDistribution=theme_list,
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
