# embedding service and pipeline functions
# uses sentence-transformers (all-MiniLM-L6-v2, 384 dims) to embed
# conversations, journals, and incoming runtime journals

import logging
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

sys.path.insert(0, str(Path(__file__).parent.parent))
from preprocessing.base_preprocessor import BasePreprocessor

# columns that every embedded journal parquet must have
JOURNAL_EMBEDDING_SCHEMA = [
    "journal_id",
    "patient_id",
    "therapist_id",
    "entry_date",
    "content",
    "word_count",
    "char_count",
    "sentence_count",
    "avg_word_length",
    "day_of_week",
    "week_number",
    "month",
    "year",
    "days_since_last",
    "embedding_text",
    "embedding",
    "embedding_model",
    "embedding_dim",
    "is_embedded",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# core service

class EmbeddingService:

    def __init__(self, model_name: Optional[str] = None, batch_size: int = 64):
        self.settings = config.settings
        self.model_name = model_name or self.settings.EMBEDDING_MODEL
        self.batch_size = batch_size
        self.model = None
        self.embedding_dim = None

    # caches the model so we only load once
    def load_model(self) -> SentenceTransformer:
        if self.model is not None:
            return self.model

        logger.info(f"Loading embedding model: {self.model_name}")
        start = time.time()
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        elapsed = time.time() - start
        logger.info(f"Model loaded in {elapsed:.2f}s | Embedding dimension: {self.embedding_dim}")
        return self.model

    # encodes in batches and logs progress every 10 batches
    def embed_texts(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        self.load_model()

        if not texts:
            logger.warning("Empty text list provided — returning empty array")
            return np.array([]).reshape(0, self.embedding_dim)

        total = len(texts)
        num_batches = (total + self.batch_size - 1) // self.batch_size
        logger.info(f"Embedding {total} texts in {num_batches} batches (batch_size={self.batch_size})")

        all_embeddings = []
        start = time.time()

        for i in range(0, total, self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            embeddings = self.model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_embeddings.append(embeddings)

            if show_progress and (batch_num % 10 == 0 or batch_num == num_batches):
                elapsed = time.time() - start
                rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
                logger.info(f"  Batch {batch_num}/{num_batches} | {i + len(batch)}/{total} texts | {rate:.0f} texts/sec")

        result = np.vstack(all_embeddings)
        total_time = time.time() - start
        logger.info(f"Embedding complete: {total} texts in {total_time:.2f}s | Shape: {result.shape}")
        return result

    def embed_dataframe(self, df: pd.DataFrame, text_column: str) -> pd.DataFrame:
        if text_column not in df.columns:
            raise ValueError(f"Column '{text_column}' not found in DataFrame")

        texts = df[text_column].fillna("").astype(str).tolist()
        embeddings = self.embed_texts(texts)

        df = df.copy()
        df["embedding"] = [emb.tolist() for emb in embeddings]
        logger.info(f"Added 'embedding' column ({self.embedding_dim} dims) to DataFrame")
        return df


# pipeline functions for batch embedding

def embed_conversations(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    model_name: Optional[str] = None,
    batch_size: int = 64,
    skip_existing: bool = True,
    force: bool = False,
) -> Path:
    settings = config.settings
    settings.ensure_directories()

    if input_path is None:
        input_path = settings.PROCESSED_DATA_DIR / "conversations" / "processed_conversations.parquet"
    if output_path is None:
        output_path = settings.PROCESSED_DATA_DIR / "conversations" / "embedded_conversations.parquet"

    if not force and skip_existing and output_path.exists():
        logger.info(f"Embedded conversations already exist: {output_path}")
        return output_path

    if not input_path.exists():
        raise FileNotFoundError(f"Processed conversation data not found: {input_path}. Run ConversationPreprocessor first.")

    logger.info(f"Loading processed conversations from {input_path}")
    df = pd.read_parquet(input_path)
    logger.info(f"Loaded {len(df)} conversations")

    text_column = "embedding_text"
    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found. Ensure ConversationPreprocessor.create_embedding_text() was called.")

    service = EmbeddingService(model_name=model_name, batch_size=batch_size)
    df = service.embed_dataframe(df, text_column=text_column)

    df["embedding_model"] = service.model_name
    df["embedding_dim"] = service.embedding_dim
    df["is_embedded"] = True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df)} embedded conversations to {output_path}")
    return output_path


def embed_journals(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    model_name: Optional[str] = None,
    batch_size: int = 64,
    skip_existing: bool = True,
    force: bool = False,
) -> Path:
    settings = config.settings
    settings.ensure_directories()

    if input_path is None:
        input_path = settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
    if output_path is None:
        output_path = settings.PROCESSED_DATA_DIR / "journals" / "embedded_journals.parquet"

    if not force and skip_existing and output_path.exists():
        logger.info(f"Embedded journals already exist: {output_path}")
        return output_path

    if not input_path.exists():
        raise FileNotFoundError(f"Processed journal data not found: {input_path}. Run JournalPreprocessor first.")

    logger.info(f"Loading processed journals from {input_path}")
    df = pd.read_parquet(input_path)
    logger.info(f"Loaded {len(df)} journal entries")

    text_column = "embedding_text"
    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found. Ensure JournalPreprocessor.create_embedding_text() was called.")

    service = EmbeddingService(model_name=model_name, batch_size=batch_size)
    df = service.embed_dataframe(df, text_column=text_column)

    df["embedding_model"] = service.model_name
    df["embedding_dim"] = service.embedding_dim
    df["is_embedded"] = True

    for col in JOURNAL_EMBEDDING_SCHEMA:
        if col not in df.columns:
            df[col] = None
    df = df[JOURNAL_EMBEDDING_SCHEMA]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df)} embedded journal entries to {output_path}")
    return output_path


# preprocesses raw incoming journals before embedding
# used for runtime journal ingestion (not the batch pipeline)
def _preprocess_journal_df(df: pd.DataFrame) -> pd.DataFrame:
    preprocessor = BasePreprocessor()

    df["content"] = df["content"].fillna("").astype(str)
    df["content"] = df["content"].apply(preprocessor.process)

    stats = df["content"].apply(preprocessor.compute_statistics)
    df["word_count"] = stats.apply(lambda x: x.word_count)
    df["char_count"] = stats.apply(lambda x: x.char_count)
    df["sentence_count"] = stats.apply(lambda x: x.sentence_count)
    df["avg_word_length"] = stats.apply(lambda x: x.avg_word_length)

    if "entry_date" in df.columns:
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
        valid = df["entry_date"].notna()
        df.loc[valid, "day_of_week"] = df.loc[valid, "entry_date"].dt.dayofweek
        df.loc[valid, "week_number"] = df.loc[valid, "entry_date"].dt.isocalendar().week
        df.loc[valid, "month"] = df.loc[valid, "entry_date"].dt.month
        df.loc[valid, "year"] = df.loc[valid, "entry_date"].dt.year
    else:
        df["entry_date"] = pd.NaT

    if "patient_id" in df.columns and "entry_date" in df.columns:
        df = df.sort_values(["patient_id", "entry_date"]).reset_index(drop=True)
        df["days_since_last"] = (
            df.groupby("patient_id")["entry_date"].diff().dt.days
        )
        df["days_since_last"] = df["days_since_last"].fillna(0).astype(int)
    else:
        df["days_since_last"] = 0

    df["embedding_text"] = df.apply(
        lambda row: f"[{row['entry_date'].strftime('%Y-%m-%d')}] {row['content']}"
        if pd.notna(row.get("entry_date"))
        else row["content"],
        axis=1,
    )

    return df

# runtime incoming journal embedding
# accepts a list of dicts or dataframe, preprocesses, embeds, and returns dataframe
# used by dag 2 (incoming_journals_pipeline) — no file i/o
def embed_incoming_journals(
    journals,
    model_name: Optional[str] = None,
    batch_size: int = 64,
) -> pd.DataFrame:
    if isinstance(journals, list):
        df = pd.DataFrame(journals)
    elif isinstance(journals, pd.DataFrame):
        df = journals.copy()
    else:
        raise TypeError(f"Expected list or DataFrame, got {type(journals)}")

    if df.empty:
        logger.warning("No journals to embed — returning empty DataFrame")
        return df

    required_cols = ["journal_id", "patient_id", "content"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if "therapist_id" not in df.columns:
        df["therapist_id"] = None

    # ensure entry_date is a pandas Timestamp for downstream embedding/stats
    if "entry_date" in df.columns:
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")

    df = _preprocess_journal_df(df)

    service = EmbeddingService(model_name=model_name, batch_size=batch_size)
    df = service.embed_dataframe(df, text_column="embedding_text")

    df["embedding_model"] = service.model_name
    df["embedding_dim"] = service.embedding_dim
    df["is_embedded"] = True

    for col in JOURNAL_EMBEDDING_SCHEMA:
        if col not in df.columns:
            df[col] = None
    df = df[JOURNAL_EMBEDDING_SCHEMA]

    # sanitize dataframe so returned records are JSON-serializable when pushed via XCom
    import numpy as np

    def _sanitize_cell(v):
        # pandas Timestamp -> ISO string
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        # pandas/np NA -> None
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        if isinstance(v, (np.generic,)):
            return v.item()
        # arrays/ndarrays -> lists
        if hasattr(v, "tolist") and not isinstance(v, (str, bytes)):
            try:
                return v.tolist()
            except Exception:
                pass
        return v

    # apply sanitize across dataframe (avoid converting embedding lists)
    for c in df.columns:
        if c == "embedding":
            # ensure embeddings are lists (not numpy arrays)
            df[c] = df[c].apply(lambda x: x.tolist() if hasattr(x, "tolist") and not isinstance(x, list) else x)
        else:
            df[c] = df[c].apply(_sanitize_cell)

    logger.info(f"Embedded {len(df)} incoming journal entries")
    return df
