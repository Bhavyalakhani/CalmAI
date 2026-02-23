# configuration for bertopic model pipeline
# prompt templates, hyperparameter search spaces, model paths

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config


# gemini prompt for generating topic labels
# bertopic passes [DOCUMENTS] and [KEYWORDS] placeholders
JOURNAL_LABEL_PROMPT = """I have a topic from a mental health patient journal dataset.
The topic contains the following documents:
[DOCUMENTS]
The topic is described by the following keywords: [KEYWORDS]

This is a mental health therapy context where patients write short journal entries.
Based on the information above, generate a short, clinically descriptive topic label of at most 6 words.
Make sure it is in the following format:
topic: <topic label>
"""

CONVERSATION_LABEL_PROMPT = """I have a topic from a mental health counseling conversation dataset.
The topic contains the following documents:
[DOCUMENTS]
The topic is described by the following keywords: [KEYWORDS]

These are patient concerns shared with therapists in counseling sessions.
Based on the information above, generate a short, clinically descriptive topic label of at most 6 words.
Make sure it is in the following format:
topic: <topic label>
"""

SEVERITY_LABEL_PROMPT = """I have a cluster of mental health counseling conversations.
The cluster contains the following documents:
[DOCUMENTS]
The cluster is described by the following keywords: [KEYWORDS]

These are patient messages from counseling sessions grouped by semantic similarity.
Based on the emotional intensity, urgency, and clinical risk indicators in these conversations,
classify this cluster into exactly ONE severity level:

- crisis: immediate danger, suicidal ideation, self-harm, acute psychotic episodes, abuse situations
- severe: intense distress, inability to cope, major depression, trauma responses, substance dependency, eating disorders
- moderate: persistent mood issues, relationship problems, grief, work stress, anxiety, anger, sleep problems
- mild: adjustment concerns, personal growth, minor worry, life transitions, communication issues, general guidance

Respond with ONLY the severity level in this format:
topic: <severity level>
"""


@dataclass
class HyperparameterSpace:
    """search space for hyperparameter tuning"""
    umap_n_neighbors: List[int] = field(default_factory=lambda: [10, 15, 20])
    umap_n_components: List[int] = field(default_factory=lambda: [3, 5])
    hdbscan_min_cluster_size: List[int] = field(default_factory=lambda: [5, 8, 10])
    hdbscan_min_samples: List[int] = field(default_factory=lambda: [3, 5])
    top_n_words: List[int] = field(default_factory=lambda: [5, 10])


@dataclass
class ConversationHyperparameterSpace:
    """search space for conversation model (longer docs, larger clusters)"""
    umap_n_neighbors: List[int] = field(default_factory=lambda: [10, 15, 20])
    umap_n_components: List[int] = field(default_factory=lambda: [5, 10])
    hdbscan_min_cluster_size: List[int] = field(default_factory=lambda: [10, 15, 20])
    hdbscan_min_samples: List[int] = field(default_factory=lambda: [5, 10])
    top_n_words: List[int] = field(default_factory=lambda: [10, 15])


@dataclass
class SeverityHyperparameterSpace:
    """search space for severity model (broader clusters for 4 severity levels)"""
    umap_n_neighbors: List[int] = field(default_factory=lambda: [10, 15, 20])
    umap_n_components: List[int] = field(default_factory=lambda: [3, 5])
    hdbscan_min_cluster_size: List[int] = field(default_factory=lambda: [15, 20, 30])
    hdbscan_min_samples: List[int] = field(default_factory=lambda: [5, 10])
    top_n_words: List[int] = field(default_factory=lambda: [10, 15])


@dataclass
class TopicModelConfig:
    """configuration for a single topic model training run"""
    model_type: str = "journals"  # "journals", "conversations", or "severity"

    # umap
    umap_n_neighbors: int = 15
    umap_n_components: int = 5
    umap_min_dist: float = 0.0
    umap_metric: str = "cosine"
    umap_random_state: int = 42

    # hdbscan
    hdbscan_min_cluster_size: int = 10
    hdbscan_min_samples: int = 5
    hdbscan_metric: str = "euclidean"
    hdbscan_cluster_selection_method: str = "eom"

    # vectorizer
    vectorizer_stop_words: str = "english"
    vectorizer_min_df: int = 2
    vectorizer_ngram_range: tuple = (1, 2)

    # bertopic
    top_n_words: int = 10
    nr_topics: Optional[int] = None  # auto
    calculate_probabilities: bool = True

    # representation
    use_gemini_labels: bool = True
    gemini_api_key: str = ""
    gemini_model: str = ""

    # paths
    embedding_model_name: str = ""

    def __post_init__(self):
        if not self.gemini_api_key:
            self.gemini_api_key = config.settings.GEMINI_API_KEY
        if not self.gemini_model:
            self.gemini_model = config.settings.GEMINI_MODEL
        if not self.embedding_model_name:
            self.embedding_model_name = config.settings.EMBEDDING_MODEL

    def to_dict(self) -> Dict[str, Any]:
        """convert to dict for mlflow logging (exclude secrets)"""
        return {
            "model_type": self.model_type,
            "umap_n_neighbors": self.umap_n_neighbors,
            "umap_n_components": self.umap_n_components,
            "umap_min_dist": self.umap_min_dist,
            "umap_metric": self.umap_metric,
            "umap_random_state": self.umap_random_state,
            "hdbscan_min_cluster_size": self.hdbscan_min_cluster_size,
            "hdbscan_min_samples": self.hdbscan_min_samples,
            "hdbscan_metric": self.hdbscan_metric,
            "hdbscan_cluster_selection_method": self.hdbscan_cluster_selection_method,
            "vectorizer_stop_words": self.vectorizer_stop_words,
            "vectorizer_min_df": self.vectorizer_min_df,
            "vectorizer_ngram_range": str(self.vectorizer_ngram_range),
            "top_n_words": self.top_n_words,
            "calculate_probabilities": self.calculate_probabilities,
            "use_gemini_labels": self.use_gemini_labels,
            "gemini_model": self.gemini_model,
            "embedding_model_name": self.embedding_model_name,
        }


def get_models_dir(model_type: str = "journals") -> Path:
    """get the directory for saving/loading topic models"""
    if model_type == "journals":
        model_dir = config.settings.PROJECT_ROOT / "models" / "bertopic_journals" / "latest"
    elif model_type == "severity":
        model_dir = config.settings.PROJECT_ROOT / "models" / "bertopic_severity" / "latest"
    else:
        model_dir = config.settings.PROJECT_ROOT / "models" / "bertopic_conversations" / "latest"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def get_reports_dir() -> Path:
    """get the directory for model reports"""
    reports_dir = config.settings.REPORTS_DIR / "model"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_mlruns_dir() -> Path:
    """get the directory for mlflow tracking"""
    mlruns_dir = config.settings.PROJECT_ROOT / "mlruns"
    mlruns_dir.mkdir(parents=True, exist_ok=True)
    return mlruns_dir
