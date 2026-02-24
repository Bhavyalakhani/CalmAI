# dashboard router — aggregate stats and mood trend for therapist overview
# therapist-only stats endpoint, mood trend accessible by therapists and patients (own data)

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.models.dashboard import DashboardStats, TrendDataPoint
from app.services.db import Database, get_db
from app.dependencies import require_role, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _resolve_pipeline_ids(user_ids: list[str], db: Database) -> list[str]:
    """resolve mongodb objectids to pipeline patient_ids"""
    from bson import ObjectId
    pipeline_ids = []
    try:
        obj_ids = [ObjectId(uid) for uid in user_ids]
        cursor = db.users.find({"_id": {"$in": obj_ids}}, {"pipeline_patient_id": 1})
        async for doc in cursor:
            pid = doc.get("pipeline_patient_id")
            if pid:
                pipeline_ids.append(pid)
    except Exception:
        pass
    return pipeline_ids


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: dict = Depends(require_role("therapist")),
    db: Database = Depends(get_db),
):
    """get aggregate dashboard statistics for the therapist"""

    patient_ids = current_user.get("patient_ids", [])

    total_patients = len(patient_ids)
    total_conversations = await db.conversations.count_documents({})

    # count journals for this therapist's patients — include pipeline ids
    pipeline_ids = await _resolve_pipeline_ids(patient_ids, db)
    all_ids = patient_ids + pipeline_ids
    journal_query = {}
    if all_ids:
        journal_query["patient_id"] = {"$in": all_ids}
    total_journals = await db.journals.count_documents(journal_query)

    # avg entries per patient
    avg_entries = round(total_journals / total_patients, 1) if total_patients > 0 else 0.0

    # active patients — those with entries in the last 7 days
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    active_patients = 0
    if all_ids:
        pipeline = [
            {"$match": {"patient_id": {"$in": all_ids}, "entry_date": {"$gte": seven_days_ago}}},
            {"$group": {"_id": "$patient_id"}},
            {"$count": "active"},
        ]
        result = await db.journals.aggregate(pipeline).to_list(length=1)
        if result:
            active_patients = result[0].get("active", 0)

    return DashboardStats(
        totalPatients=total_patients,
        totalJournals=total_journals,
        totalConversations=total_conversations,
        avgEntriesPerPatient=avg_entries,
        activePatients=active_patients,
    )


@router.get("/mood-trend/{patient_id}", response_model=list[TrendDataPoint])
async def get_mood_trend(
    patient_id: str,
    days: int = Query(14, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """get mood trend data points for a patient over the last N days.
    accessible by therapists (for their patients) and patients (for themselves)."""

    # access control: therapists can view their patients, patients can view their own
    if current_user["role"] == "therapist":
        if patient_id not in current_user.get("patient_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this patient",
            )
    elif current_user["role"] == "patient":
        if patient_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own mood trend",
            )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # resolve pipeline id for the patient
    from bson import ObjectId as _ObjId
    pipeline_id = patient_id
    try:
        user = await db.users.find_one({"_id": _ObjId(patient_id)}, {"pipeline_patient_id": 1})
        if user and user.get("pipeline_patient_id"):
            pipeline_id = user["pipeline_patient_id"]
    except Exception:
        pass

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    now_str = datetime.now(timezone.utc).isoformat()

    cursor = db.journals.find(
        {
            "patient_id": {"$in": [patient_id, pipeline_id]},
            "entry_date": {"$gte": cutoff, "$lte": now_str},
        },
        {"entry_date": 1, "mood": 1, "_id": 0},
    ).sort("entry_date", 1)

    mood_labels = {1: "Very Low", 2: "Low", 3: "Moderate", 4: "Good", 5: "Great"}
    # aggregate by unique day — average mood if multiple entries on the same day
    day_moods: dict[str, list[float]] = {}
    async for doc in cursor:
        mood = doc.get("mood")
        entry_date = doc.get("entry_date", "")
        if isinstance(entry_date, str):
            date_str = entry_date[:10]
        else:
            date_str = str(entry_date)[:10]

        if mood is not None:
            import math
            val = float(mood)
            if not math.isnan(val):
                day_moods.setdefault(date_str, []).append(val)

    trend = []
    for date_str in sorted(day_moods):
        values = day_moods[date_str]
        if not values:
            continue
        avg_mood = round(sum(values) / len(values), 1)
        trend.append(TrendDataPoint(
            date=date_str,
            value=avg_mood,
            label=mood_labels.get(round(avg_mood), "Unknown"),
        ))

    return trend
