#!/usr/bin/env python3
"""seed incoming_journals in mongodb to trigger dag 2's conditional retrain.

usage (from vm or local):
  python seed_for_retrain.py                    # seed 60 entries (hits 50-entry threshold)
  python seed_for_retrain.py --count 10         # seed 10 entries only
  python seed_for_retrain.py --force-retrain    # backdate training metadata to trigger time threshold
  python seed_for_retrain.py --count 60 --force-retrain  # both triggers
  python seed_for_retrain.py --status           # show current db state (no changes)

after seeding, trigger dag 2 from the airflow ui or wait for the 12h schedule.
the conditional_retrain task checks: 50+ new entries OR 7+ days since last training.
"""

import argparse
import hashlib
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# add src and configs to path (works both locally and inside docker)
src_dir = Path(__file__).parent / "src"
configs_dir = Path(__file__).parent / "configs"
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(configs_dir))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_for_retrain")

# sample journal entries covering diverse mental health topics
SAMPLE_ENTRIES = [
    {"content": "Today was a tough day at work. My manager criticized my presentation in front of everyone and I felt so embarrassed. I could not stop thinking about it on the drive home.", "patient_id": "patient_001", "mood": 2},
    {"content": "I went for a long walk in the park this morning. The birds were singing and the air was fresh. It reminded me of childhood summers. For the first time in weeks I felt genuinely calm and present.", "patient_id": "patient_002", "mood": 4},
    {"content": "I had an argument with my partner again about finances. We keep going in circles. I feel like we're stuck and I don't know how to break the pattern.", "patient_id": "patient_003", "mood": 2},
    {"content": "Therapy session went well today. We talked about setting boundaries with my family. I realized I've been saying yes to everything because I'm afraid of disappointing them.", "patient_id": "patient_004", "mood": 4},
    {"content": "Couldn't sleep last night. Kept replaying the conversation with my friend who said I was being selfish. Maybe they're right. I feel like I'm always letting people down.", "patient_id": "patient_005", "mood": 1},
    {"content": "Started a new meditation practice this week. Only five minutes a day but it helps me notice when my thoughts are spiraling. Today I caught myself catastrophizing about a deadline.", "patient_id": "patient_001", "mood": 3},
    {"content": "My anxiety has been really bad this week. I've been avoiding phone calls and canceling plans. I know isolation makes it worse but I just can't face people right now.", "patient_id": "patient_006", "mood": 1},
    {"content": "Had a really good day today. Finished a project I've been putting off for months. The sense of accomplishment is amazing. I need to remember this feeling when I'm struggling.", "patient_id": "patient_007", "mood": 5},
    {"content": "I've been thinking about my relationship with food lately. I notice I eat more when I'm stressed and then feel guilty about it. It's a cycle I want to understand better.", "patient_id": "patient_008", "mood": 3},
    {"content": "Took my dog to the beach today. Watching him run through the waves made me smile for the first time all week. Sometimes simple things really do help.", "patient_id": "patient_009", "mood": 4},
    {"content": "Woke up feeling heavy today. The grief comes in waves and today it hit hard. I miss my grandmother so much. Even small things like making tea remind me of her.", "patient_id": "patient_010", "mood": 1},
    {"content": "Group therapy was unexpectedly helpful. Hearing others share similar struggles made me feel less alone. I spoke up for the first time and people were supportive.", "patient_id": "patient_002", "mood": 4},
    {"content": "I noticed I've been doom-scrolling on my phone before bed. It definitely makes my anxiety worse. Going to try leaving my phone outside the bedroom starting tonight.", "patient_id": "patient_003", "mood": 2},
    {"content": "My sister called today and we had a genuine conversation for the first time in months. No judgment, no unsolicited advice. Just listening. It felt healing.", "patient_id": "patient_005", "mood": 4},
    {"content": "Had a panic attack at the grocery store. It came out of nowhere. I had to leave my cart and sit in the car until it passed. Feeling frustrated with myself.", "patient_id": "patient_006", "mood": 1},
    {"content": "Journaling has become a real anchor for me. Even on days when I don't know what to write I just start and something comes out. Today I realized how much progress I've made.", "patient_id": "patient_004", "mood": 4},
    {"content": "Work stress is building up again. The new project has impossible deadlines and I don't want to let the team down. I can feel the tension in my shoulders constantly.", "patient_id": "patient_007", "mood": 2},
    {"content": "Tried the breathing exercise my therapist taught me during a meeting today. Nobody noticed but it helped me stay grounded when my boss started raising his voice.", "patient_id": "patient_008", "mood": 3},
    {"content": "I've been avoiding looking at my bank account. The financial anxiety is real but ignoring it only makes it worse. Tomorrow I'm going to sit down and face the numbers.", "patient_id": "patient_009", "mood": 2},
    {"content": "Today I set a boundary with a coworker who always dumps extra work on me. It was uncomfortable but I did it. My therapist would be proud. I'm proud of myself.", "patient_id": "patient_010", "mood": 5},
]


def seed_entries(count: int = 60) -> int:
    """insert test journal entries into incoming_journals collection."""
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()

        entries = []
        for i in range(count):
            template = SAMPLE_ENTRIES[i % len(SAMPLE_ENTRIES)]
            timestamp = datetime.now(timezone.utc) - timedelta(hours=i)
            hash_input = f"{template['patient_id']}:{template['content']}:{timestamp.isoformat()}"
            journal_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]

            entries.append({
                "journal_id": journal_id,
                "patient_id": template["patient_id"],
                "therapist_id": "therapist_001",
                "content": template["content"],
                "entry_date": timestamp.isoformat(),
                "mood": template["mood"],
                "prompt_id": None,
                "is_processed": False,
            })

        inserted = 0
        for entry in entries:
            try:
                client.incoming_journals.update_one(
                    {"journal_id": entry["journal_id"]},
                    {"$set": entry},
                    upsert=True,
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert {entry['journal_id']}: {e}")

        logger.info(f"Seeded {inserted}/{count} entries into incoming_journals")
        return inserted
    finally:
        client.close()


def force_stale_metadata():
    """backdate training metadata to 10 days ago so the 7-day threshold triggers."""
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        client.save_training_metadata({
            "journal_count": 0,
            "conversation_count": 0,
            "trained_at": old_date,
            "reason": "forced_stale_for_testing",
        })
        logger.info(f"Backdated training metadata to {old_date}")
    finally:
        client.close()


def show_status():
    """show current db state relevant to conditional retrain."""
    from storage.mongodb_client import MongoDBClient

    client = MongoDBClient()
    try:
        client.connect()

        unprocessed = client.incoming_journals.count_documents({"is_processed": False})
        processed = client.incoming_journals.count_documents({"is_processed": True})
        total_journals = client.journals.count_documents({})
        total_conversations = client.conversations.count_documents({})

        last_training = client.get_last_training_metadata()

        print(f"\n{'='*50}")
        print("  DAG 2 retrain status")
        print(f"{'='*50}")
        print(f"  incoming_journals (unprocessed): {unprocessed}")
        print(f"  incoming_journals (processed):   {processed}")
        print(f"  journals collection:             {total_journals}")
        print(f"  conversations collection:        {total_conversations}")
        print()

        if last_training:
            print(f"  last training:")
            print(f"    trained_at:        {last_training.get('trained_at', 'unknown')}")
            print(f"    journal_count:     {last_training.get('journal_count', 0)}")
            print(f"    conversation_count:{last_training.get('conversation_count', 0)}")
            print(f"    reason:            {last_training.get('reason', 'unknown')}")

            new_entries = total_journals - last_training.get("journal_count", 0)
            print(f"\n  new entries since last training: {new_entries} (threshold: 50)")

            trained_at = last_training.get("trained_at")
            if trained_at:
                try:
                    trained_dt = datetime.fromisoformat(trained_at.replace("Z", "+00:00"))
                    days_since = (datetime.now(timezone.utc) - trained_dt).days
                    print(f"  days since last training:        {days_since} (threshold: 7)")
                    will_retrain = new_entries >= 50 or days_since >= 7
                    print(f"\n  will retrain: {'YES' if will_retrain else 'NO'}")
                except Exception:
                    pass
        else:
            print("  no training metadata found (first run)")

        print(f"{'='*50}\n")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed incoming_journals for DAG 2 conditional retrain testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python seed_for_retrain.py                     # seed 60 entries (hits threshold)
  python seed_for_retrain.py --count 10          # seed 10 entries
  python seed_for_retrain.py --force-retrain     # backdate training metadata
  python seed_for_retrain.py --status            # check current state
  python seed_for_retrain.py --count 60 --force-retrain  # both triggers
        """,
    )
    parser.add_argument("--count", type=int, default=60, help="Number of entries to seed (default: 60)")
    parser.add_argument("--force-retrain", action="store_true", help="Backdate training metadata to trigger 7-day threshold")
    parser.add_argument("--status", action="store_true", help="Show current DB state without making changes")

    args = parser.parse_args()

    if args.status:
        show_status()
        sys.exit(0)

    seeded = seed_entries(args.count)
    if args.force_retrain:
        force_stale_metadata()

    print(f"\nDone. Seeded {seeded} entries.")
    if args.force_retrain:
        print("Training metadata backdated — both entry and time thresholds should trigger.")
    print("\nNext: trigger DAG 2 from Airflow UI or run:")
    print("  python run_incoming_pipeline.py")
    print("\nCheck status with:")
    print("  python seed_for_retrain.py --status")
