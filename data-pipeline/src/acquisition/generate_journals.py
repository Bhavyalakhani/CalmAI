# generates synthetic journal entries using gemini api
# each of the 10 patient profiles gets 100 entries spanning ~300 days
# handles fetching, raw json parsing with fallback regex, and parquet export

import time
import json
import logging
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta

import yaml
import pandas as pd
import google.genai as genai
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class JournalGenerator:
    PROMPT = """You are a creative writer simulating realistic therapy journal entries for a mental health app demo.

PATIENT PROFILE:
- Name: {name}
- Age: {age}
- Occupation: {occupation}
- Background: {background}
- Primary concerns: {concerns}
- Writing style: {writing_style}

TASK:
Generate exactly 100 journal entries spanning from {start_date} to {end_date}.

GUIDELINES:
1. Each entry should be 20-30 words
2. Write in first person as the patient
3. Include specific daily events, interactions, thoughts and feelings
4. Show realistic emotional progression - include good days, bad days, setbacks and breakthroughs
5. Reference their specific concerns naturally throughout
6. Match the patient's unique writing style and voice
7. Space entries 2-4 days apart realistically
8. Mention therapy sessions occasionally (roughly every 2 weeks)
9. Include mundane daily details mixed with emotional content
10. Never break character or mention being an AI

RESPOND WITH ONLY A VALID JSON ARRAY IN THIS EXACT FORMAT:
[
  {{"entry_number": 1, "date": "2025-06-01", "content": "Journal entry text here..."}},
  {{"entry_number": 2, "date": "2025-06-03", "content": "Journal entry text here..."}},
  ...continue for all 100 entries...
]

Generate the 100 entries as a JSON array now:"""

    def __init__(self):
        self.settings = config.settings
        self.logger = logger
        self.client = None
        self.cfg = None

    def load_config(self):
        config_path = self.settings.CONFIGS_DIR / "patient_profiles.yaml"
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
        return self.cfg

    def get_end_date(self, start_date):
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = start + timedelta(days=300)
        return end.strftime("%Y-%m-%d")

    def get_raw_responses_dir(self):
        raw_dir = self.settings.RAW_DATA_DIR / "journals" / "raw_responses"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir

    def get_output_path(self):
        return self.settings.RAW_DATA_DIR / "journals" / "synthetic_journals.parquet"

    # api call with 3 retries, 10s backoff between failures
    def fetch_patient_response(self, patient):
        start_date = patient["start_date"]
        end_date = self.get_end_date(start_date)
        prompt = self.PROMPT.format(
            name=patient["name"],
            age=patient["age"],
            occupation=patient["occupation"],
            background=patient["background"],
            concerns=", ".join(patient["concerns"]),
            writing_style=patient["writing_style"],
            start_date=start_date,
            end_date=end_date
        )

        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.settings.GEMINI_MODEL,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0.9,
                        max_output_tokens=100000
                    )
                )

                if response.text:
                    return response.text
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(10)
                else:
                    raise

        return None

    def save_raw_response(self, patient_id, response_text, raw_dir):
        output_path = raw_dir / f"{patient_id}_raw.json"
        data = {
            "patient_id": patient_id,
            "timestamp": datetime.now().isoformat(),
            "raw_response": response_text
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.info(f"  Saved raw response to {output_path}")
        return output_path

    def fetch_all(self, skip_existing=True):
        self.settings.ensure_directories()
        self.load_config()
        patients = self.cfg["patients"]

        if not self.settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set")

        self.client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
        raw_dir = self.get_raw_responses_dir()

        self.logger.info(f"Fetching journals for {len(patients)} patients")
        self.logger.info(f"Raw responses will be saved to: {raw_dir}")

        fetched_count = 0
        skipped_count = 0

        for i, patient in enumerate(patients):
            patient_id = patient['patient_id']
            raw_file = raw_dir / f"{patient_id}_raw.json"

            if skip_existing and raw_file.exists():
                self.logger.info(f"[{i+1}/{len(patients)}] {patient_id} - SKIPPED (already exists)")
                skipped_count += 1
                continue

            self.logger.info(f"[{i+1}/{len(patients)}] {patient_id} ({patient['name']}) - Fetching...")

            response_text = self.fetch_patient_response(patient)

            if response_text:
                self.save_raw_response(patient_id, response_text, raw_dir)
                fetched_count += 1
            else:
                self.logger.error(f"Failed to get response for {patient_id}")

            if i < len(patients) - 1 and response_text:
                self.logger.info("Waiting 15s...")
                time.sleep(15)

        self.logger.info(f"\nFETCH COMPLETE!")
        self.logger.info(f"Fetched: {fetched_count}")
        self.logger.info(f"Skipped: {skipped_count}")
        self.logger.info(f"Raw files location: {raw_dir}")

        return raw_dir

    # tries json.loads first, then regex extraction, then trailing comma fix
    def parse_json_response(self, response_text):
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            pattern = r'\{\s*"entry_number"\s*:\s*(\d+)\s*,\s*"date"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}'
            matches = re.findall(pattern, text, re.DOTALL)

            if matches:
                entries = []
                for entry_num, date, content in matches:
                    content = content.replace('\n', ' ').strip()
                    entries.append({
                        "entry_number": int(entry_num),
                        "date": date,
                        "content": content
                    })
                if entries:
                    self.logger.info(f"  Recovered {len(entries)} entries via regex extraction")
                    return entries
        except Exception as e:
            self.logger.warning(f"Regex extraction failed: {e}")

        try:
            fixed = re.sub(r',\s*([}\]])', r'\1', text)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        self.logger.error(f"JSON parse error after all recovery attempts")
        self.logger.error(f"Response preview: {text[:1000]}...")
        raise json.JSONDecodeError("Failed to parse JSON after multiple attempts", text, 0)

    # normalizes keys (gemini sometimes uses different names) and filters empties
    def process_entries(self, parsed, patient_id, therapist_id):
        entries = []
        for idx, item in enumerate(parsed):
            # try several possible key names since gemini isn't always consistent
            entry_num = (
                item.get('entry_number') or
                item.get('entryNumber') or
                item.get('entry_num') or
                item.get('number') or
                (idx + 1)
            )

            date = (
                item.get('date') or
                item.get('entry_date') or
                item.get('entryDate') or
                ''
            )

            content = (
                item.get('content') or
                item.get('entry') or
                item.get('text') or
                item.get('journal_entry') or
                ''
            )

            if not content:
                self.logger.warning(f"Entry {entry_num} has no content, skipping")
                continue

            entries.append({
                "journal_id": f"{patient_id}_entry_{int(entry_num):03d}",
                "patient_id": patient_id,
                "therapist_id": therapist_id,
                "entry_date": date,
                "content": content,
                "word_count": len(content.split())
            })

        return entries

    def parse_all(self, skip_existing=True):
        self.settings.ensure_directories()

        output_path = self.get_output_path()
        if skip_existing and output_path.exists():
            self.logger.info(f"Output file already exists: {output_path}")
            self.logger.info("Skipping parse. Use --force to regenerate.")
            return output_path

        self.load_config()
        therapist_id = self.cfg["therapist_id"]

        raw_dir = self.get_raw_responses_dir()

        self.logger.info(f"Parsing raw responses from: {raw_dir}")

        all_entries = []
        success_count = 0
        error_count = 0

        raw_files = list(raw_dir.glob("*_raw.json"))
        self.logger.info(f"Found {len(raw_files)} raw response files")

        for raw_file in raw_files:
            patient_id = raw_file.stem.replace("_raw", "")
            self.logger.info(f"Parsing {patient_id}...")

            try:
                with open(raw_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                raw_response = data["raw_response"]
                parsed = self.parse_json_response(raw_response)
                self.logger.info(f"Parsed {len(parsed)} entries")

                entries = self.process_entries(parsed, patient_id, therapist_id)
                all_entries.extend(entries)
                self.logger.info(f"Processed {len(entries)} entries")

                success_count += 1

            except Exception as e:
                self.logger.error(f"Failed to parse {patient_id}: {e}")
                error_count += 1

        if not all_entries:
            self.logger.error("No entries parsed! Check raw files.")
            return None

        df = pd.DataFrame(all_entries)
        output_path = self.get_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)

        self.logger.info(f"PARSE COMPLETE!")
        self.logger.info(f"Success: {success_count}")
        self.logger.info(f"Errors: {error_count}")
        self.logger.info(f"Total entries: {len(df)}")
        self.logger.info(f"Patients: {df['patient_id'].nunique()}")
        self.logger.info(f"Avg words: {df['word_count'].mean():.0f}")
        self.logger.info(f"Output: {output_path}")

        return output_path

    def run(self, skip_existing=True):
        output_path = self.get_output_path()
        if skip_existing and output_path.exists():
            self.logger.info(f"Final output already exists: {output_path}")
            self.logger.info("Skipping generation. Use --force to regenerate.")
            return output_path

        self.fetch_all(skip_existing=skip_existing)
        return self.parse_all(skip_existing=False)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic journal entries")
    parser.add_argument(
        "command",
        choices=["fetch", "parse", "run"],
        nargs="?",
        default="run",
    )
    parser.add_argument(
        "--force",
        action="store_true",
    )
    args = parser.parse_args()

    generator = JournalGenerator()

    if args.command == "fetch":
        generator.fetch_all(skip_existing=not args.force)
    elif args.command == "parse":
        generator.parse_all(skip_existing=not args.force)
    else:
        generator.run(skip_existing=not args.force)


if __name__ == "__main__":
    main()