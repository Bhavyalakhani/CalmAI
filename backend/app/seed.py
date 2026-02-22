# seed script — creates initial users in mongodb
# maps to the 10 patient profiles from data-pipeline + 1 therapist
# run once: python -m app.seed

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.services.db import db
from app.services.auth_service import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# default password for all seed users
DEFAULT_PASSWORD = "calmai123"


async def seed():
    """create therapist + 10 patient users matching data-pipeline profiles"""
    await db.connect()

    # check if users already exist
    existing = await db.users.count_documents({})
    if existing > 0:
        logger.info(f"Database already has {existing} users — skipping seed")
        await db.close()
        return

    hashed_pw = hash_password(DEFAULT_PASSWORD)
    now = datetime.now(timezone.utc).isoformat()

    # create therapist
    therapist_doc = {
        "email": "dr.chen@calmai.com",
        "hashed_password": hashed_pw,
        "name": "Dr. Sarah Chen",
        "role": "therapist",
        "avatar_url": None,
        "created_at": "2024-06-15T00:00:00Z",
        "specialization": "Cognitive Behavioral Therapy",
        "license_number": "PSY-2024-11892",
        "practice_name": "Mindful Path Clinic",
        "patient_ids": [],  # will be populated after patients are created
    }

    therapist_result = await db.users.insert_one(therapist_doc)
    therapist_id = str(therapist_result.inserted_id)
    logger.info(f"Created therapist: Dr. Sarah Chen (id: {therapist_id})")

    # patient profiles matching data-pipeline/configs/patient_profiles.yaml
    patients = [
        {"patient_id": "patient_001", "name": "Alex Rivera", "email": "alex.rivera@email.com", "dob": "1997-03-12", "onboarded": "2025-06-01T00:00:00Z"},
        {"patient_id": "patient_002", "name": "Jordan Kim", "email": "jordan.kim@email.com", "dob": "1981-08-25", "onboarded": "2025-05-15T00:00:00Z"},
        {"patient_id": "patient_003", "name": "Sam Patel", "email": "sam.patel@email.com", "dob": "2006-11-03", "onboarded": "2025-04-01T00:00:00Z"},
        {"patient_id": "patient_004", "name": "Morgan Blake", "email": "morgan.blake@email.com", "dob": "1973-05-17", "onboarded": "2025-06-15T00:00:00Z"},
        {"patient_id": "patient_005", "name": "Riley Nguyen", "email": "riley.nguyen@email.com", "dob": "1991-09-30", "onboarded": "2025-05-01T00:00:00Z"},
        {"patient_id": "patient_006", "name": "Casey Thompson", "email": "casey.thompson@email.com", "dob": "1987-02-14", "onboarded": "2025-07-01T00:00:00Z"},
        {"patient_id": "patient_007", "name": "Taylor Davis", "email": "taylor.davis@email.com", "dob": "2001-07-22", "onboarded": "2025-05-20T00:00:00Z"},
        {"patient_id": "patient_008", "name": "Jamie Wilson", "email": "jamie.wilson@email.com", "dob": "1984-12-05", "onboarded": "2025-06-10T00:00:00Z"},
        {"patient_id": "patient_009", "name": "Avery Martinez", "email": "avery.martinez@email.com", "dob": "1994-04-18", "onboarded": "2025-04-15T00:00:00Z"},
        {"patient_id": "patient_010", "name": "Quinn Anderson", "email": "quinn.anderson@email.com", "dob": "1963-10-08", "onboarded": "2025-05-10T00:00:00Z"},
    ]

    patient_ids = []
    for p in patients:
        patient_doc = {
            "email": p["email"],
            "hashed_password": hashed_pw,
            "name": p["name"],
            "role": "patient",
            "avatar_url": None,
            "created_at": p["onboarded"],
            "therapist_id": therapist_id,
            "date_of_birth": p["dob"],
            "onboarded_at": p["onboarded"],
            # store the data-pipeline patient_id for journal linking
            "pipeline_patient_id": p["patient_id"],
        }
        result = await db.users.insert_one(patient_doc)
        patient_id = str(result.inserted_id)
        patient_ids.append(patient_id)
        logger.info(f"Created patient: {p['name']} (id: {patient_id}, pipeline_id: {p['patient_id']})")

    # link all patients to the therapist
    await db.users.update_one(
        {"_id": therapist_result.inserted_id},
        {"$set": {"patient_ids": patient_ids}},
    )
    logger.info(f"Linked {len(patient_ids)} patients to therapist")

    # create indexes on users collection
    await db.users.create_index("email", unique=True)
    await db.users.create_index("role")
    await db.users.create_index("pipeline_patient_id")
    logger.info("Created indexes on users collection")

    logger.info("Seed complete!")
    await db.close()


if __name__ == "__main__":
    asyncio.run(seed())
