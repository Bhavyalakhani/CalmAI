# preprocesses therapist-patient conversation datasets
# standardizes columns from two different huggingface sources,
# generates content-hash ids, computes text stats, creates embedding text

import logging
import hashlib
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .base_preprocessor import BasePreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ConversationPreprocessor:
    
    def __init__(self):
        self.settings = config.settings
        self.preprocessor = BasePreprocessor()
        self.df = None
    
    # paths
    def get_input_dir(self) -> Path:
        return self.settings.RAW_DATA_DIR / "conversations"

    def get_output_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "conversations" / "processed_conversations.parquet"

    # loading — counsel_chat loaded first so its richer metadata (context_title) is preserved on dedup
    def load_data(self) -> pd.DataFrame:
        input_dir = self.get_input_dir()
        
        frames = []
        for parquet_file in sorted(input_dir.glob("*.parquet")):
            df = pd.read_parquet(parquet_file)
            df["source_file"] = parquet_file.stem
            frames.append(df)
            logger.info(f"Loaded {len(df)} records from {parquet_file.name}")
        
        if not frames:
            raise FileNotFoundError(f"No parquet files found in {input_dir}")
        
        self.df = pd.concat(frames, ignore_index=True)
        logger.info(f"Total records loaded: {len(self.df)}")
        return self.df
    
    # remap counsel-chat columns (questionText -> context, answerText -> response)
    def standardize_columns(self) -> pd.DataFrame:
        column_mapping = {}
        for col in self.df.columns:
            column_mapping[col] = col.lower().replace(" ", "_")
        
        self.df = self.df.rename(columns=column_mapping)
        
        if "questiontext" in self.df.columns and "context" not in self.df.columns:
            self.df = self.df.rename(columns={
                "questiontext": "context",
                "questiontitle": "context_title",
                "answertext": "response"
            })
        
        return self.df
    
    # md5 hash of context + response (with separator to avoid boundary collisions)
    def generate_ids(self) -> pd.DataFrame:
        def create_hash(row):
            content = f"{row.get('context', '')}|||{row.get('response', '')}"
            return hashlib.md5(content.encode()).hexdigest()[:12]
        
        self.df["conversation_id"] = self.df.apply(create_hash, axis=1)
        
        # only remove exact content duplicates (same context AND same response)
        duplicates = self.df["conversation_id"].duplicated()
        if duplicates.any():            
            n_dupes = duplicates.sum()
            self.df = self.df[~duplicates].reset_index(drop=True)
            logger.info(f"Removed {n_dupes} exact content duplicates (same context + same response)")
        
        return self.df
    
    # run base preprocessor + compute word/char/sentence counts
    def apply_preprocessing(self) -> pd.DataFrame:
        text_columns = ["context", "response"]
        
        for col in text_columns:
            if col not in self.df.columns:
                continue
            
            self.df[col] = self.df[col].fillna("").astype(str)
            self.df[col] = self.df[col].apply(self.preprocessor.process)
            
            stats = self.df[col].apply(self.preprocessor.compute_statistics)
            self.df[f"{col}_word_count"] = stats.apply(lambda x: x.word_count)
            self.df[f"{col}_char_count"] = stats.apply(lambda x: x.char_count)
            self.df[f"{col}_sentence_count"] = stats.apply(lambda x: x.sentence_count)
            self.df[f"{col}_avg_word_length"] = stats.apply(lambda x: x.avg_word_length)
        
        self.df["is_embedded"] = False
        return self.df
    
    # format: "User concern: {context}\n\nCounselor response: {response}"
    def create_embedding_text(self) -> pd.DataFrame:
        def format_embedding(row):
            context = row.get("context", "")
            response = row.get("response", "")
            return f"User concern: {context}\n\nCounselor response: {response}"
        
        self.df["embedding_text"] = self.df.apply(format_embedding, axis=1)
        return self.df
    
    # filter out rows with empty text or too-short content
    def validate(self) -> bool:
        issues = []
        
        empty_context = (self.df["context"].str.strip() == "").sum()
        if empty_context > 0:
            issues.append(f"Empty context fields: {empty_context}")
        
        empty_response = (self.df["response"].str.strip() == "").sum()
        if empty_response > 0:
            issues.append(f"Empty response fields: {empty_response}")
        
        min_word_count = 3
        short_context = (self.df["context_word_count"] < min_word_count).sum()
        if short_context > 0:
            issues.append(f"Context with <{min_word_count} words: {short_context}")
        
        short_response = (self.df["response_word_count"] < min_word_count).sum()
        if short_response > 0:
            issues.append(f"Response with <{min_word_count} words: {short_response}")
        
        empty_embedding = (self.df["embedding_text"].str.strip() == "").sum()
        if empty_embedding > 0:
            issues.append(f"Empty embedding_text fields: {empty_embedding}")
        
        if issues:
            for issue in issues:
                logger.warning(issue)
            
            valid_mask = (
                (self.df["context"].str.strip() != "") &
                (self.df["response"].str.strip() != "") &
                (self.df["context_word_count"] >= min_word_count) &
                (self.df["response_word_count"] >= min_word_count) &
                (self.df["embedding_text"].str.strip() != "")
            )
            original_count = len(self.df)
            self.df = self.df[valid_mask].reset_index(drop=True)
            logger.info(f"Filtered {original_count - len(self.df)} invalid records")
        
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
        
        logger.info("Step 1/6: Loading raw data")
        self.load_data()
        logger.info(f"{len(self.df)} records loaded")
        
        logger.info("Step 2/6: Standardizing columns")
        self.standardize_columns()
        logger.info(f"Columns: {list(self.df.columns)}")
        
        logger.info("Step 3/6: Generating IDs and deduplicating")
        before_dedup = len(self.df)
        self.generate_ids()
        logger.info(f"{before_dedup} → {len(self.df)} records (removed {before_dedup - len(self.df)} duplicates)")
        
        logger.info("Step 4/6: Applying text preprocessing + feature engineering")
        self.apply_preprocessing()
        logger.info(f"Added word_count, char_count, sentence_count, avg_word_length for context & response")
        
        logger.info("Step 5/6: Creating embedding text")
        self.create_embedding_text()
        logger.info(f"embedding_text column created")
        
        logger.info("Step 6/6: Validating and filtering")
        before_validate = len(self.df)
        self.validate()
        logger.info(f"{before_validate} → {len(self.df)} records (filtered {before_validate - len(self.df)} invalid)")
        
        return self.save()


if __name__ == "__main__":
    preprocessor = ConversationPreprocessor()
    preprocessor.run(skip_existing=False)
