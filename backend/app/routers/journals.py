# journals router — list journals and submit new entries
# patients see their own, therapists see their patients' journals

import logging
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from bson import ObjectId

from app.models.journal import JournalCreate, JournalEntryResponse, JournalSubmitResponse
from app.services.db import Database, get_db
from app.dependencies import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/journals", tags=["journals"])


async def _resolve_pipeline_id(user_id: str, db: Database) -> str:
    """resolve a mongodb objectid to pipeline patient_id (e.g. 'patient_001')"""
    from bson import ObjectId as _ObjId
    try:
        user = await db.users.find_one({"_id": _ObjId(user_id)}, {"pipeline_patient_id": 1})
        if user and user.get("pipeline_patient_id"):
            return user["pipeline_patient_id"]
    except Exception:
        pass
    return user_id


async def _resolve_pipeline_ids(user_ids: list[str], db: Database) -> list[str]:
    """resolve a list of mongodb objectids to pipeline patient_ids"""
    from bson import ObjectId as _ObjId
    pipeline_ids = []
    try:
        obj_ids = [_ObjId(uid) for uid in user_ids]
        cursor = db.users.find({"_id": {"$in": obj_ids}}, {"pipeline_patient_id": 1})
        async for doc in cursor:
            pid = doc.get("pipeline_patient_id")
            if pid:
                pipeline_ids.append(pid)
    except Exception:
        pass
    return pipeline_ids

# lazy-loaded topic model inference (singleton)
_topic_inference = None
_topic_inference_loaded = False

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _get_topic_inference():
    """lazy-load the journal topic model for real-time classification.
    returns None if model is not available (themes will be unclassified)."""
    global _topic_inference, _topic_inference_loaded
    if _topic_inference_loaded:
        return _topic_inference
    _topic_inference_loaded = True
    try:
        from pathlib import Path
        import sys
        # add data-pipeline src to path for topic_modeling imports
        dp_src = Path(__file__).resolve().parents[3] / "data-pipeline" / "src"
        if str(dp_src) not in sys.path:
            sys.path.insert(0, str(dp_src))
        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference(model_type="journals")
        if inf.load():
            _topic_inference = inf
            logger.info("Journal topic model loaded for real-time classification")
        else:
            logger.info("Journal topic model not available, themes will be unclassified")
    except Exception as e:
        logger.warning(f"Could not load topic model: {e}, themes will be unclassified")
    return _topic_inference


def _classify_themes(text: str) -> list[str]:
    """classify journal text into topics using trained bertopic model.
    returns unclassified if model is not available."""
    inf = _get_topic_inference()
    if inf is not None:
        try:
            result = inf.predict_single(text)
            if result and result.get("topic_id", -1) != -1:
                label = result.get("label", "")
                if label:
                    return [label]
        except Exception:
            pass

    return ["unclassified"]


async def _doc_to_journal(doc: dict, db: Database | None = None) -> JournalEntryResponse:
    """convert a mongodb journal document to response model.
    if themes are missing and BERTopic classifies them, persist back to db."""
    journal_id = doc.get("journal_id", str(doc.get("_id", "")))

    # parse entry_date
    entry_date = doc.get("entry_date", "")
    if entry_date and not isinstance(entry_date, str):
        entry_date = str(entry_date)

    # get themes - either from doc or classify once and persist
    themes = doc.get("themes", [])
    if not themes and doc.get("content"):
        themes = _classify_themes(doc["content"])
        # persist so we never re-classify this journal
        if db is not None and doc.get("_id"):
            try:
                await db.journals.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"themes": themes}},
                )
            except Exception:
                pass  # non-critical, will retry next request

    # day of week mapping
    day_of_week = doc.get("day_of_week")
    if day_of_week is not None and isinstance(day_of_week, (int, float)):
        try:
            day_of_week = DAY_NAMES[int(day_of_week)]
        except (IndexError, ValueError):
            day_of_week = None

    return JournalEntryResponse(
        id=journal_id,
        patientId=doc.get("patient_id", ""),
        content=doc.get("content", ""),
        entryDate=entry_date,
        themes=themes,
        wordCount=doc.get("word_count", 0),
        charCount=doc.get("char_count", 0),
        sentenceCount=doc.get("sentence_count", 0),
        avgWordLength=doc.get("avg_word_length", 0.0),
        mood=doc.get("mood"),
        dayOfWeek=day_of_week,
        weekNumber=doc.get("week_number"),
        month=doc.get("month"),
        year=doc.get("year"),
        daysSinceLast=doc.get("days_since_last"),
        isEmbedded=doc.get("is_embedded", False),
    )


@router.get("", response_model=list[JournalEntryResponse])
async def list_journals(
    patient_id: str = Query(None, alias="patientId", description="filter by patient id"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """list journal entries. patients see their own, therapists see their patients' journals."""

    query = {}

    if current_user["role"] == "patient":
        # patients can only see their own journals — try pipeline id first
        pipeline_id = current_user.get("pipeline_patient_id", current_user["id"])
        query["patient_id"] = {"$in": [current_user["id"], pipeline_id]}
    elif current_user["role"] == "therapist":
        if patient_id:
            # verify therapist owns this patient
            if patient_id not in current_user.get("patient_ids", []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this patient's journals",
                )
            # resolve pipeline id for the patient
            pipeline_id = await _resolve_pipeline_id(patient_id, db)
            query["patient_id"] = {"$in": [patient_id, pipeline_id]}
        else:
            # show all of therapist's patients' journals
            patient_id_list = current_user.get("patient_ids", [])
            if patient_id_list:
                pipeline_ids = await _resolve_pipeline_ids(patient_id_list, db)
                query["patient_id"] = {"$in": patient_id_list + pipeline_ids}
            else:
                return []

    cursor = db.journals.find(query).sort("entry_date", -1).skip(skip).limit(limit)
    journals = []
    async for doc in cursor:
        journals.append(await _doc_to_journal(doc, db))

    return journals


@router.post("", response_model=JournalSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_journal(
    body: JournalCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """submit a new journal entry (writes to incoming_journals for dag 2 processing)"""

    # only patients can submit journals
    if current_user["role"] != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can submit journal entries",
        )

    now = datetime.now(timezone.utc)

    # generate journal_id as md5 hash of patient_id + content + timestamp
    raw = f"{current_user['id']}:{body.content}:{now.isoformat()}"
    journal_id = hashlib.md5(raw.encode()).hexdigest()[:12]

    # use pipeline_patient_id so dag 2 analytics stay consistent
    pipeline_id = current_user.get("pipeline_patient_id", current_user["id"])

    doc = {
        "journal_id": journal_id,
        "patient_id": pipeline_id,
        "therapist_id": current_user.get("therapist_id", ""),
        "content": body.content,
        "entry_date": now.isoformat(),
        "mood": body.mood,
        "is_processed": False,
    }

    await db.incoming_journals.insert_one(doc)
    logger.info(f"Journal submitted: {journal_id} by patient {current_user['id']}")

    return JournalSubmitResponse(journalId=journal_id)
