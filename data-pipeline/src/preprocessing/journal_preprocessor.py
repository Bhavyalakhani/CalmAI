# preprocesses synthetic journal entries
# parses dates, computes text stats, adds temporal features
# (day_of_week, week_number, month, year, days_since_last)

import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .base_preprocessor import BasePreprocessor
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class JournalPreprocessor:
    
    def __init__(self):
        self.settings = config.settings
        self.preprocessor = BasePreprocessor()
        self.df = None
    
    # paths
    def get_input_path(self) -> Path:
        return self.settings.RAW_DATA_DIR / "journals" / "synthetic_journals.parquet"

    def get_output_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"

    # loading
    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Journal data not found: {input_path}")
        
        self.df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(self.df)} journal entries")
        return self.df
    
    # date parsing — invalid dates (e.g. feb 29 in non-leap year) get forward-filled per patient
    def parse_dates(self) -> pd.DataFrame:
        if "entry_date" in self.df.columns:
            self.df["entry_date"] = pd.to_datetime(self.df["entry_date"], errors="coerce")
            
            invalid_dates = self.df["entry_date"].isna().sum()
            if invalid_dates > 0:
                logger.warning(f"Found {invalid_dates} invalid dates, forward-filling per patient")
                self.df["entry_date"] = (
                    self.df.groupby("patient_id")["entry_date"]
                    .transform(lambda s: s.ffill().bfill())
                )
                still_null = self.df["entry_date"].isna().sum()
                if still_null > 0:
                    logger.warning(f"  {still_null} dates still null after fill")
        
        return self.df
    
    # text preprocessing and stats
    def apply_preprocessing(self) -> pd.DataFrame:
        self.df["content"] = self.df["content"].fillna("").astype(str)
        self.df["content"] = self.df["content"].apply(self.preprocessor.process)
        
        stats = self.df["content"].apply(self.preprocessor.compute_statistics)
        self.df["word_count"] = stats.apply(lambda x: x.word_count)
        self.df["char_count"] = stats.apply(lambda x: x.char_count)
        self.df["sentence_count"] = stats.apply(lambda x: x.sentence_count)
        self.df["avg_word_length"] = stats.apply(lambda x: x.avg_word_length)
        
        self.df["is_embedded"] = False
        return self.df
    
    # temporal feature engineering
    def add_temporal_features(self) -> pd.DataFrame:
        if "entry_date" not in self.df.columns:
            return self.df
        
        valid_dates = self.df["entry_date"].notna()
        
        self.df.loc[valid_dates, "day_of_week"] = self.df.loc[valid_dates, "entry_date"].dt.dayofweek
        self.df.loc[valid_dates, "week_number"] = self.df.loc[valid_dates, "entry_date"].dt.isocalendar().week
        self.df.loc[valid_dates, "month"] = self.df.loc[valid_dates, "entry_date"].dt.month
        self.df.loc[valid_dates, "year"] = self.df.loc[valid_dates, "entry_date"].dt.year
        
        return self.df
    
    # gap between entries per patient (first entry = 0)
    def calculate_days_since_last(self) -> pd.DataFrame:
        if "entry_date" not in self.df.columns or "patient_id" not in self.df.columns:
            return self.df
        
        self.df = self.df.sort_values(["patient_id", "entry_date"]).reset_index(drop=True)
        
        self.df["days_since_last"] = (
            self.df.groupby("patient_id")["entry_date"]
            .diff()
            .dt.days
        )
        
        self.df["days_since_last"] = self.df["days_since_last"].fillna(0).astype(int)
        
        return self.df
    
    # format: "[YYYY-MM-DD] content" if date exists, else just content
    def create_embedding_text(self) -> pd.DataFrame:
        def format_embedding(row):
            date_str = ""
            if pd.notna(row.get("entry_date")):
                date_str = row["entry_date"].strftime("%Y-%m-%d")
            content = row.get("content", "")
            return f"[{date_str}] {content}" if date_str else content
        
        self.df["embedding_text"] = self.df.apply(format_embedding, axis=1)
        return self.df
    
    # removes duplicates and empty content
    def validate(self) -> bool:
        required_columns = ["journal_id", "patient_id", "content"]
        missing = [col for col in required_columns if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        duplicate_ids = self.df["journal_id"].duplicated().sum()
        if duplicate_ids > 0:
            logger.warning(f"Found {duplicate_ids} duplicate journal IDs")
            self.df = self.df.drop_duplicates(subset=["journal_id"]).reset_index(drop=True)
        
        patient_counts = self.df.groupby("patient_id").size()
        sparse_patients = patient_counts[patient_counts < 5]
        if len(sparse_patients) > 0:
            logger.warning(f"Found {len(sparse_patients)} patients with fewer than 5 entries")
        
        empty_content = (self.df["content"].str.strip() == "").sum()
        if empty_content > 0:
            logger.warning(f"Found {empty_content} entries with empty content")
            self.df = self.df[self.df["content"].str.strip() != ""].reset_index(drop=True)
        
        if "embedding_text" in self.df.columns:
            empty_embedding = (self.df["embedding_text"].str.strip() == "").sum()
            if empty_embedding > 0:
                logger.warning(f"Found {empty_embedding} entries with empty embedding_text")
                self.df = self.df[self.df["embedding_text"].str.strip() != ""].reset_index(drop=True)
        
        return True
    
    def save(self) -> Path:
        output_path = self.get_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(self.df)} records to {output_path}")
        return output_path
    
    def run(self, skip_existing: bool = True) -> Path:
        self.settings.ensure_directories()
        
        output_path = self.get_output_path()
        if skip_existing and output_path.exists():
            logger.info(f"Output already exists: {output_path}")
            return output_path
        
        logger.info("Step 1/7: Loading raw journal data")
        self.load_data()
        logger.info(f"{len(self.df)} entries loaded")
        
        logger.info("Step 2/7: Parsing dates")
        self.parse_dates()
        valid_dates = self.df["entry_date"].notna().sum() if "entry_date" in self.df.columns else 0
        logger.info(f"{valid_dates} valid dates parsed")
        
        logger.info("Step 3/7: Applying text preprocessing + feature engineering")
        self.apply_preprocessing()
        logger.info(f"Added word_count, char_count, sentence_count, avg_word_length")
        
        logger.info("Step 4/7: Adding temporal features")
        self.add_temporal_features()
        logger.info(f"Added day_of_week, week_number, month, year")
        
        logger.info("Step 5/7: Calculating days_since_last per patient")
        self.calculate_days_since_last()
        logger.info(f"days_since_last computed for {self.df['patient_id'].nunique()} patients")
        
        logger.info("Step 6/7: Creating embedding text")
        self.create_embedding_text()
        logger.info(f"embedding_text column created")
        
        logger.info("Step 7/7: Validating and filtering")
        before_validate = len(self.df)
        self.validate()
        logger.info(f"{before_validate} → {len(self.df)} entries (filtered {before_validate - len(self.df)} invalid)")
        
        return self.save()


def process_incoming_journals(journals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Preprocess a list of incoming journal dicts in-memory and return list of records.

    Reuses the same sequence of steps as `JournalPreprocessor.run` but without
    writing to disk. This is suitable for the micro-batch DAG where entries are
    passed via XComs.
    """
    import time

    t0 = time.time()
    if not journals:
        logging.getLogger(__name__).warning("process_incoming_journals called with empty list")
        return []

    df = pd.DataFrame(journals)
    pre = JournalPreprocessor()
    pre.df = df.copy()

    logger.info(f"Step 1/7: Loaded {len(pre.df)} incoming journals into DataFrame")

    logger.info("Step 2/7: Parsing dates")
    pre.parse_dates()
    valid_dates = pre.df['entry_date'].notna().sum() if 'entry_date' in pre.df.columns else 0
    logger.info(f"  Parsed dates — {valid_dates} valid dates")

    logger.info("Step 3/7: Applying text preprocessing + stats")
    pre.apply_preprocessing()
    logger.info("  Text preprocessing complete")

    logger.info("Step 4/7: Adding temporal features")
    pre.add_temporal_features()
    logger.info("  Temporal features added")

    logger.info("Step 5/7: Calculating days_since_last per patient")
    pre.calculate_days_since_last()
    logger.info("  days_since_last computed")

    logger.info("Step 6/7: Creating embedding text")
    pre.create_embedding_text()
    logger.info("  embedding_text created")

    logger.info("Step 7/7: Validating and filtering records")
    before_validate = len(pre.df)
    pre.validate()
    logger.info(f"  Validation complete: {before_validate} → {len(pre.df)} entries")

    records = pre.df.to_dict("records")

    def _sanitize_value(v):
        # pd.Timestamp -> ISO string (covers entry_date)
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        # NA / NaT / None -> None
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        # numpy scalar -> python native
        if isinstance(v, np.generic):
            return v.item()
        # pandas extension scalar e.g. UInt32 from isocalendar (covers week_number)
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            try:
                return v.item()
            except Exception:
                pass
        if isinstance(v, (list, tuple)):
            return [_sanitize_value(x) for x in v]
        if hasattr(v, "tolist") and not isinstance(v, (str, bytes)):
            try:
                return v.tolist()
            except Exception:
                pass
        return v

    safe_records = [{k: _sanitize_value(v) for k, v in r.items()} for r in records]

    elapsed = round(time.time() - t0, 2)
    logging.getLogger(__name__).info(f"Processed {len(safe_records)} incoming journals in {elapsed}s")
    return safe_records



if __name__ == "__main__":
    preprocessor = JournalPreprocessor()
    preprocessor.run(skip_existing=False)
