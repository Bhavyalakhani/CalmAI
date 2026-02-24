# journals router — list journals and submit new entries
# patients see their own, therapists see their patients' journals

import logging
import hashlib
import math
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


async def _refresh_patient_analytics(patient_id: str, db: Database, deleted_journal_id: str | None = None):
    """lightweight analytics refresh from the journals collection.
    recomputes total_entries, avg_word_count, entry_frequency, date_range
    and cleans up representative_entries. runs instantly in the backend
    so the frontend shows updated stats without waiting for dag 2.
    topic_distribution counts are adjusted proportionally."""
    try:
        # fetch all journals for this patient
        cursor = db.journals.find(
            {"patient_id": patient_id},
            {"content": 1, "entry_date": 1, "word_count": 1, "journal_id": 1},
        )
        journals = []
        async for doc in cursor:
            journals.append(doc)

        total_entries = len(journals)

        # avg word count
        word_counts = [j.get("word_count", len(str(j.get("content", "")).split())) for j in journals]
        avg_word_count = round(sum(word_counts) / max(1, len(word_counts)), 1) if word_counts else 0

        # entry frequency by month
        entry_frequency = {}
        dates = []
        for j in journals:
            ed = j.get("entry_date", "")
            if ed:
                try:
                    dt = datetime.fromisoformat(str(ed).replace("Z", "+00:00"))
                    month_key = dt.strftime("%Y-%m")
                    entry_frequency[month_key] = entry_frequency.get(month_key, 0) + 1
                    dates.append(dt)
                except Exception:
                    pass

        # date range
        date_range = None
        if dates:
            min_dt = min(dates)
            max_dt = max(dates)
            date_range = {
                "first": min_dt.isoformat(),
                "last": max_dt.isoformat(),
                "span_days": (max_dt - min_dt).days,
            }

        # build the update doc
        update_fields = {
            "total_entries": total_entries,
            "avg_word_count": avg_word_count,
            "entry_frequency": entry_frequency,
            "date_range": date_range,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # read existing analytics doc to adjust topic_distribution + representative_entries
        existing = await db.patient_analytics.find_one({"patient_id": patient_id})
        if existing:
            old_total = existing.get("total_entries", 0)

            # adjust topic_distribution counts proportionally
            raw_topics = existing.get("topic_distribution", [])
            if raw_topics and old_total > 0 and total_entries != old_total:
                ratio = total_entries / old_total
                for t in raw_topics:
                    t["count"] = max(0, round(t.get("count", 0) * ratio))
                    t["percentage"] = round(t["count"] / max(1, total_entries) * 100, 1)
                update_fields["topic_distribution"] = raw_topics

            # clean up representative_entries — remove deleted journal
            if deleted_journal_id:
                raw_repr = existing.get("representative_entries", [])
                update_fields["representative_entries"] = [
                    r for r in raw_repr if r.get("journal_id") != deleted_journal_id
                ]

        await db.patient_analytics.update_one(
            {"patient_id": patient_id},
            {"$set": update_fields},
            upsert=True,
        )
        logger.info(f"Analytics refreshed for patient {patient_id}: {total_entries} entries")
    except Exception as e:
        # non-critical — dag 2 will do a full recomputation
        logger.warning(f"Could not refresh analytics for {patient_id}: {e}")


async def _doc_to_journal(doc: dict, db: Database | None = None) -> JournalEntryResponse:
    """convert a mongodb journal document to response model.
    if themes are missing and BERTopic classifies them, persist back to db."""
    journal_id = doc.get("journal_id", str(doc.get("_id", "")))

    # parse entry_date
    entry_date = doc.get("entry_date", "")
    if entry_date and not isinstance(entry_date, str):
        entry_date = str(entry_date)

    # get themes - either from doc or classify once and persist
    # skip classification for unprocessed entries (dag 2 will assign proper topics)
    themes = doc.get("themes", [])
    is_embedded = doc.get("is_embedded", True)
    if not themes and doc.get("content"):
        if not is_embedded:
            # entry hasn't been through dag 2 yet — show placeholder
            themes = ["processing"]
        else:
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

    # sanitize mood — mongoDB may store NaN which pydantic rejects
    raw_mood = doc.get("mood")
    if raw_mood is not None:
        try:
            if isinstance(raw_mood, float) and math.isnan(raw_mood):
                raw_mood = None
            else:
                raw_mood = int(raw_mood)
        except (ValueError, TypeError):
            raw_mood = None

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
        mood=raw_mood,
        promptId=doc.get("prompt_id"),
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

    # exclude future-dated entries (e.g. seeded/dummy data)
    now_str = datetime.now(timezone.utc).isoformat()
    query["entry_date"] = {"$lte": now_str}

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
        "prompt_id": body.prompt_id,
        "is_processed": False,
    }

    await db.incoming_journals.insert_one(doc)

    # write a preliminary doc to journals collection so the entry appears
    # immediately in the frontend (dag 2 will upsert with full processing later)
    preliminary_doc = {
        "journal_id": journal_id,
        "patient_id": pipeline_id,
        "therapist_id": current_user.get("therapist_id", ""),
        "content": body.content,
        "entry_date": now.isoformat(),
        "mood": body.mood,
        "prompt_id": body.prompt_id,
        "word_count": len(body.content.split()),
        "char_count": len(body.content),
        "sentence_count": max(1, body.content.count(".") + body.content.count("!") + body.content.count("?")),
        "avg_word_length": round(sum(len(w) for w in body.content.split()) / max(1, len(body.content.split())), 1),
        "themes": [],
        "is_embedded": False,
    }
    await db.journals.insert_one(preliminary_doc)

    logger.info(f"Journal submitted: {journal_id} by patient {current_user['id']}")

    # if responding to a prompt, mark the prompt as responded
    if body.prompt_id:
        try:
            result = await db.prompts.update_one(
                {"prompt_id": body.prompt_id, "patient_id": current_user["id"], "status": "pending"},
                {"$set": {
                    "status": "responded",
                    "response_journal_id": journal_id,
                    "responded_at": now.isoformat(),
                }},
            )
            if result.matched_count > 0:
                logger.info(f"Prompt {body.prompt_id} marked as responded")
            else:
                logger.warning(f"Prompt {body.prompt_id} not found or already responded")
        except Exception as e:
            logger.warning(f"Could not update prompt status: {e}")

    # refresh analytics so frontend shows updated stats immediately
    await _refresh_patient_analytics(pipeline_id, db)

    return JournalSubmitResponse(journalId=journal_id)


@router.patch("/{journal_id}", response_model=JournalEntryResponse)
async def edit_journal(
    journal_id: str,
    body: JournalCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """edit an existing journal entry. re-stages to incoming_journals for reprocessing."""

    if current_user["role"] != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can edit journal entries",
        )

    pipeline_id = current_user.get("pipeline_patient_id", current_user["id"])

    # find the journal
    journal = await db.journals.find_one({
        "journal_id": journal_id,
        "patient_id": {"$in": [current_user["id"], pipeline_id]},
    })
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    now = datetime.now(timezone.utc)

    # update the journal document directly
    update_fields = {
        "content": body.content,
        "mood": body.mood,
        "themes": [],  # reset themes for re-classification
        "updated_at": now.isoformat(),
    }

    await db.journals.update_one(
        {"journal_id": journal_id},
        {"$set": update_fields},
    )

    # also re-stage to incoming_journals so dag 2 reprocesses (embedding, analytics)
    restage_doc = {
        "journal_id": journal_id,
        "patient_id": pipeline_id,
        "therapist_id": current_user.get("therapist_id", ""),
        "content": body.content,
        "entry_date": journal.get("entry_date", now.isoformat()),
        "mood": body.mood,
        "prompt_id": journal.get("prompt_id"),
        "is_processed": False,
        "is_edit": True,
    }
    await db.incoming_journals.insert_one(restage_doc)

    # remove old rag_vectors entry so dag 2 creates a fresh one
    await db.rag_vectors.delete_one({"journal_id": journal_id, "doc_type": "journal"})

    # refresh analytics so frontend shows updated stats immediately
    await _refresh_patient_analytics(pipeline_id, db)

    # fetch updated doc and return
    updated = await db.journals.find_one({"journal_id": journal_id})
    logger.info(f"Journal edited: {journal_id} by patient {current_user['id']}")
    return await _doc_to_journal(updated, db)


@router.delete("/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journal(
    journal_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """soft delete a journal entry"""

    if current_user["role"] != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can delete journal entries",
        )

    pipeline_id = current_user.get("pipeline_patient_id", current_user["id"])

    # find the journal
    journal = await db.journals.find_one({
        "journal_id": journal_id,
        "patient_id": {"$in": [current_user["id"], pipeline_id]},
    })
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    # delete from journals collection
    await db.journals.delete_one({"journal_id": journal_id})

    # delete from rag_vectors
    await db.rag_vectors.delete_one({"journal_id": journal_id, "doc_type": "journal"})

    # remove from incoming_journals if still staged
    await db.incoming_journals.delete_one({"journal_id": journal_id})

    # refresh analytics so frontend shows updated stats immediately
    await _refresh_patient_analytics(pipeline_id, db, deleted_journal_id=journal_id)

    logger.info(f"Journal deleted: {journal_id} by patient {current_user['id']}")
