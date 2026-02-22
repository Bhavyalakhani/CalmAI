# shared fixtures for backend api tests
# provides mock db, test users, auth tokens, and httpx test client

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.db import Database, get_db
from app.services.auth_service import hash_password, create_access_token
from app.dependencies import get_current_user, require_role


# test ids
THERAPIST_OID = ObjectId()
PATIENT_OID = ObjectId()
PATIENT_2_OID = ObjectId()
THERAPIST_ID = str(THERAPIST_OID)
PATIENT_ID = str(PATIENT_OID)
PATIENT_2_ID = str(PATIENT_2_OID)


# test user documents (as they'd appear from mongodb)

THERAPIST_DOC = {
    "_id": THERAPIST_OID,
    "email": "dr.chen@calmai.com",
    "hashed_password": hash_password("calmai123"),
    "name": "Dr. Sarah Chen",
    "role": "therapist",
    "avatar_url": None,
    "created_at": "2024-06-15T00:00:00Z",
    "specialization": "Cognitive Behavioral Therapy",
    "license_number": "PSY-2024-11892",
    "practice_name": "Mindful Path Clinic",
    "patient_ids": [PATIENT_ID, PATIENT_2_ID],
}

PATIENT_DOC = {
    "_id": PATIENT_OID,
    "email": "alex.rivera@email.com",
    "hashed_password": hash_password("calmai123"),
    "name": "Alex Rivera",
    "role": "patient",
    "avatar_url": None,
    "created_at": "2025-06-01T00:00:00Z",
    "therapist_id": THERAPIST_ID,
    "date_of_birth": "1997-03-12",
    "onboarded_at": "2025-06-01T00:00:00Z",
    "pipeline_patient_id": "patient_001",
}

PATIENT_2_DOC = {
    "_id": PATIENT_2_OID,
    "email": "jordan.kim@email.com",
    "hashed_password": hash_password("calmai123"),
    "name": "Jordan Kim",
    "role": "patient",
    "avatar_url": None,
    "created_at": "2025-05-15T00:00:00Z",
    "therapist_id": THERAPIST_ID,
    "date_of_birth": "1981-08-25",
    "onboarded_at": "2025-05-15T00:00:00Z",
    "pipeline_patient_id": "patient_002",
}


# sample data

SAMPLE_JOURNAL = {
    "_id": ObjectId(),
    "journal_id": "abc123def456",
    "patient_id": PATIENT_ID,
    "therapist_id": THERAPIST_ID,
    "content": "Today I felt really anxious about my work deadline. The pressure is overwhelming.",
    "entry_date": "2025-06-10T12:00:00Z",
    "word_count": 13,
    "char_count": 78,
    "sentence_count": 2,
    "avg_word_length": 5.0,
    "mood": 2,
    "day_of_week": 1,
    "week_number": 24,
    "month": 6,
    "year": 2025,
    "days_since_last": 3,
    "is_embedded": True,
}

SAMPLE_JOURNAL_2 = {
    "_id": ObjectId(),
    "journal_id": "xyz789ghi012",
    "patient_id": PATIENT_ID,
    "therapist_id": THERAPIST_ID,
    "content": "Feeling much better today. Therapy session was really helpful.",
    "entry_date": "2025-06-13T12:00:00Z",
    "word_count": 10,
    "char_count": 60,
    "sentence_count": 2,
    "avg_word_length": 5.2,
    "mood": 4,
    "day_of_week": 4,
    "week_number": 24,
    "month": 6,
    "year": 2025,
    "days_since_last": 3,
    "is_embedded": True,
}

SAMPLE_CONVERSATION = {
    "_id": ObjectId(),
    "conversation_id": "conv_abc12345",
    "context": "I've been feeling anxious about my job interview next week.",
    "response": "It's natural to feel anxious. Let's explore some coping strategies.",
    "topic": "anxiety",
    "severity": "moderate",
    "context_word_count": 11,
    "response_word_count": 11,
    "source_file": "dataset1",
}

SAMPLE_ANALYTICS = {
    "_id": ObjectId(),
    "patient_id": PATIENT_ID,
    "total_entries": 25,
    "theme_distribution": {"anxiety": 10, "work": 8, "positive": 5, "sleep": 2},
    "avg_word_count": 45.3,
    "entry_frequency": {"2025-05": 12, "2025-06": 13},
    "date_range": {"first": "2025-05-01", "last": "2025-06-13", "span_days": 43},
    "computed_at": "2025-06-14T00:00:00Z",
}


# async cursor mock

class AsyncCursorMock:
    """mock for motor's async cursor — supports async for and chained methods"""

    def __init__(self, data=None):
        self._data = data or []
        self._index = 0

    def sort(self, *args, **kwargs):
        return self

    def skip(self, n):
        self._data = self._data[n:]
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._data):
            raise StopAsyncIteration
        item = self._data[self._index]
        self._index += 1
        return item

    async def to_list(self, length=None):
        if length is not None:
            return self._data[:length]
        return self._data


class MockCollection:
    """mock for a motor collection with async methods"""

    def __init__(self, data=None):
        self._data = data or []
        self.inserted = []

    def find(self, query=None, projection=None):
        # basic query filtering
        results = self._data
        if query:
            results = [d for d in results if self._matches(d, query)]
        return AsyncCursorMock(results)

    async def find_one(self, query=None, projection=None):
        if not query:
            return self._data[0] if self._data else None
        for doc in self._data:
            if self._matches(doc, query):
                return doc
        return None

    async def insert_one(self, doc):
        oid = doc.get("_id", ObjectId())
        doc["_id"] = oid
        self._data.append(doc)
        self.inserted.append(doc)
        result = MagicMock()
        result.inserted_id = oid
        return result

    async def count_documents(self, query=None):
        if not query:
            return len(self._data)
        return len([d for d in self._data if self._matches(d, query)])

    async def update_one(self, query, update, upsert=False):
        result = MagicMock()
        result.modified_count = 0
        for doc in self._data:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$addToSet" in update:
                    for key, val in update["$addToSet"].items():
                        if key not in doc:
                            doc[key] = []
                        if val not in doc[key]:
                            doc[key].append(val)
                result.modified_count = 1
                break
        return result

    async def create_index(self, *args, **kwargs):
        return "mock_index"

    def aggregate(self, pipeline):
        # simplified aggregate — return empty cursor for stats
        return AsyncCursorMock([])

    def _matches(self, doc, query):
        """basic mongodb query matching for tests"""
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(doc, cond) for cond in value):
                    return False
                continue
            doc_val = doc.get(key)
            if isinstance(value, dict):
                if "$in" in value:
                    if doc_val not in value["$in"]:
                        return False
                elif "$gte" in value:
                    if doc_val is None or doc_val < value["$gte"]:
                        return False
                elif "$regex" in value:
                    import re
                    flags = re.IGNORECASE if value.get("$options") == "i" else 0
                    if doc_val is None or not re.search(value["$regex"], str(doc_val), flags):
                        return False
            elif doc_val != value:
                return False
        return True


class MockDatabase:
    """mock database that mimics the Database class"""

    def __init__(self):
        self.users = MockCollection([
            THERAPIST_DOC.copy(),
            PATIENT_DOC.copy(),
            PATIENT_2_DOC.copy(),
        ])
        self.journals = MockCollection([
            SAMPLE_JOURNAL.copy(),
            SAMPLE_JOURNAL_2.copy(),
        ])
        self.conversations = MockCollection([SAMPLE_CONVERSATION.copy()])
        self.incoming_journals = MockCollection([])
        self.patient_analytics = MockCollection([SAMPLE_ANALYTICS.copy()])
        self.rag_vectors = MockCollection([])
        self.pipeline_metadata = MockCollection([])
        self.invite_codes = MockCollection([])

    async def connect(self):
        pass

    async def close(self):
        pass


@pytest.fixture
def mock_db():
    """create a fresh mock database for each test"""
    return MockDatabase()


def _therapist_dict():
    """return therapist user dict as get_current_user would return"""
    doc = THERAPIST_DOC.copy()
    doc["id"] = THERAPIST_ID
    return doc


def _patient_dict():
    """return patient user dict as get_current_user would return"""
    doc = PATIENT_DOC.copy()
    doc["id"] = PATIENT_ID
    return doc


@pytest.fixture
def therapist_token():
    """jwt access token for the test therapist"""
    return create_access_token({"sub": THERAPIST_ID, "role": "therapist"})


@pytest.fixture
def patient_token():
    """jwt access token for the test patient"""
    return create_access_token({"sub": PATIENT_ID, "role": "patient"})


@pytest_asyncio.fixture
async def client(mock_db):
    """httpx async test client with mocked dependencies"""

    async def override_get_db():
        return mock_db

    async def override_get_current_user_therapist():
        return _therapist_dict()

    app.dependency_overrides[get_db] = override_get_db
    # don't override get_current_user by default — tests will set it as needed

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def therapist_client(mock_db):
    """client authenticated as a therapist"""

    async def override_get_db():
        return mock_db

    async def override_get_current_user():
        return _therapist_dict()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def patient_client(mock_db):
    """client authenticated as a patient"""

    async def override_get_db():
        return mock_db

    async def override_get_current_user():
        return _patient_dict()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
