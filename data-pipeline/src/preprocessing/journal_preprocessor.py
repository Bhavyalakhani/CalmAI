import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config # pyright: ignore[reportMissingImports]

from .base_preprocessor import BasePreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class JournalPreprocessor:
    
    def __init__(self):
        self.settings = config.settings
        self.preprocessor = BasePreprocessor()
        self.df = None
    
    def get_input_path(self) -> Path:
        return self.settings.RAW_DATA_DIR / "journals" / "synthetic_journals.parquet"
    
    def get_output_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
    
    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Journal data not found: {input_path}")
        
        self.df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(self.df)} journal entries")
        return self.df
    
    def parse_dates(self) -> pd.DataFrame:
        if "entry_date" in self.df.columns:
            self.df["entry_date"] = pd.to_datetime(self.df["entry_date"], errors="coerce")
            
            invalid_dates = self.df["entry_date"].isna().sum()
            if invalid_dates > 0:
                logger.warning(f"Found {invalid_dates} invalid dates")
        
        return self.df
    
    def apply_preprocessing(self) -> pd.DataFrame:
        self.df["content"] = self.df["content"].fillna("").astype(str)
        self.df["content"] = self.df["content"].apply(self.preprocessor.process)
        
        stats = self.df["content"].apply(self.preprocessor.compute_statistics)
        self.df["word_count"] = stats.apply(lambda x: x.word_count)
        self.df["char_count"] = stats.apply(lambda x: x.char_count)
        self.df["sentence_count"] = stats.apply(lambda x: x.sentence_count)
        
        return self.df
    
    def add_temporal_features(self) -> pd.DataFrame:
        if "entry_date" not in self.df.columns:
            return self.df
        
        valid_dates = self.df["entry_date"].notna()
        
        self.df.loc[valid_dates, "day_of_week"] = self.df.loc[valid_dates, "entry_date"].dt.dayofweek
        self.df.loc[valid_dates, "week_number"] = self.df.loc[valid_dates, "entry_date"].dt.isocalendar().week
        self.df.loc[valid_dates, "month"] = self.df.loc[valid_dates, "entry_date"].dt.month
        self.df.loc[valid_dates, "year"] = self.df.loc[valid_dates, "entry_date"].dt.year
        
        return self.df
    
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
    
    def create_embedding_text(self) -> pd.DataFrame:
        def format_embedding(row):
            date_str = ""
            if pd.notna(row.get("entry_date")):
                date_str = row["entry_date"].strftime("%Y-%m-%d")
            content = row.get("content", "")
            return f"[{date_str}] {content}" if date_str else content
        
        self.df["embedding_text"] = self.df.apply(format_embedding, axis=1)
        return self.df
    
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
        
        self.load_data()
        self.parse_dates()
        self.apply_preprocessing()
        self.add_temporal_features()
        self.calculate_days_since_last()
        self.create_embedding_text()
        self.validate()
        return self.save()


if __name__ == "__main__":
    preprocessor = JournalPreprocessor()
    preprocessor.run(skip_existing=False)
