# data drift detection for CalmAI topic models
# compares incoming data distributions against training baselines
# supports vocabulary drift, embedding drift, and topic distribution drift
#
# used by incoming_journals_pipeline (DAG 2) as an additional retraining trigger
# alongside the existing volume-based and time-based thresholds

import logging
from typing import Dict, Any, Optional, List

import numpy as np

logger = logging.getLogger(__name__)


class DriftDetector:
    """detects distribution shifts between training data and new incoming data.

    three drift signals:
    1. vocabulary drift — cosine similarity of word frequency vectors
    2. embedding drift — shift in mean embedding centroid (cosine distance)
    3. topic distribution drift — jensen-shannon divergence of topic assignments
    """

    def __init__(
        self,
        vocab_threshold: float = 0.65,
        embedding_threshold: float = 0.30,
        topic_threshold: float = 0.25,
    ):
        self.vocab_threshold = vocab_threshold
        self.embedding_threshold = embedding_threshold
        self.topic_threshold = topic_threshold

    def detect_vocabulary_drift(
        self, reference_docs: List[str], current_docs: List[str], top_n: int = 500
    ) -> Dict[str, Any]:
        """compare word frequency distributions between reference and current docs.
        returns cosine similarity (1.0 = identical, 0.0 = completely different)."""
        if not reference_docs or not current_docs:
            return {"similarity": 1.0, "drifted": False, "reason": "insufficient data"}

        ref_freq = self._word_frequencies(reference_docs)
        cur_freq = self._word_frequencies(current_docs)

        # build shared vocabulary from top-N words in each set
        ref_top = set(sorted(ref_freq, key=ref_freq.get, reverse=True)[:top_n])
        cur_top = set(sorted(cur_freq, key=cur_freq.get, reverse=True)[:top_n])
        vocab = sorted(ref_top | cur_top)

        if not vocab:
            return {"similarity": 1.0, "drifted": False, "reason": "empty vocabulary"}

        ref_vec = np.array([ref_freq.get(w, 0) for w in vocab], dtype=np.float64)
        cur_vec = np.array([cur_freq.get(w, 0) for w in vocab], dtype=np.float64)

        # normalize to probability distributions
        ref_sum = ref_vec.sum()
        cur_sum = cur_vec.sum()
        if ref_sum > 0:
            ref_vec /= ref_sum
        if cur_sum > 0:
            cur_vec /= cur_sum

        similarity = self._cosine_similarity(ref_vec, cur_vec)
        drifted = similarity < self.vocab_threshold

        return {
            "similarity": round(float(similarity), 4),
            "threshold": self.vocab_threshold,
            "drifted": drifted,
            "vocab_size": len(vocab),
            "new_words_ratio": round(len(cur_top - ref_top) / max(len(cur_top), 1), 4),
        }

    def detect_embedding_drift(
        self, reference_embeddings: np.ndarray, current_embeddings: np.ndarray
    ) -> Dict[str, Any]:
        """compare mean embedding centroids using cosine distance.
        also checks spread via mean pairwise distance to centroid."""
        if reference_embeddings.size == 0 or current_embeddings.size == 0:
            return {"distance": 0.0, "drifted": False, "reason": "insufficient embeddings"}

        ref_centroid = reference_embeddings.mean(axis=0)
        cur_centroid = current_embeddings.mean(axis=0)

        distance = 1.0 - self._cosine_similarity(ref_centroid, cur_centroid)
        drifted = distance > self.embedding_threshold

        # measure spread change (ratio of mean distances to centroid)
        ref_spread = np.mean(np.linalg.norm(reference_embeddings - ref_centroid, axis=1))
        cur_spread = np.mean(np.linalg.norm(current_embeddings - cur_centroid, axis=1))
        spread_ratio = cur_spread / max(ref_spread, 1e-8)

        return {
            "centroid_distance": round(float(distance), 4),
            "threshold": self.embedding_threshold,
            "drifted": drifted,
            "ref_spread": round(float(ref_spread), 4),
            "cur_spread": round(float(cur_spread), 4),
            "spread_ratio": round(float(spread_ratio), 4),
        }

    def detect_topic_drift(
        self, reference_topics: List[int], current_topics: List[int], num_topics: int
    ) -> Dict[str, Any]:
        """compare topic assignment distributions using jensen-shannon divergence.
        JSD ranges from 0 (identical) to 1 (completely different)."""
        if not reference_topics or not current_topics:
            return {"jsd": 0.0, "drifted": False, "reason": "insufficient topics"}

        # include outlier topic (-1) in the distribution
        min_topic = min(min(reference_topics), min(current_topics), -1)
        max_topic = max(max(reference_topics), max(current_topics), num_topics)
        n_bins = max_topic - min_topic + 1

        ref_hist = np.zeros(n_bins, dtype=np.float64)
        cur_hist = np.zeros(n_bins, dtype=np.float64)

        for t in reference_topics:
            ref_hist[t - min_topic] += 1
        for t in current_topics:
            cur_hist[t - min_topic] += 1

        # normalize to probability distributions
        ref_sum = ref_hist.sum()
        cur_sum = cur_hist.sum()
        if ref_sum > 0:
            ref_hist /= ref_sum
        if cur_sum > 0:
            cur_hist /= cur_sum

        jsd = self._jensen_shannon_divergence(ref_hist, cur_hist)
        drifted = jsd > self.topic_threshold

        # count novel topics (in current but not in reference)
        ref_topic_set = set(reference_topics) - {-1}
        cur_topic_set = set(current_topics) - {-1}
        novel_topics = cur_topic_set - ref_topic_set

        return {
            "jsd": round(float(jsd), 4),
            "threshold": self.topic_threshold,
            "drifted": drifted,
            "ref_topic_count": len(ref_topic_set),
            "cur_topic_count": len(cur_topic_set),
            "novel_topics": len(novel_topics),
        }

    def run_drift_check(
        self,
        reference_docs: Optional[List[str]] = None,
        current_docs: Optional[List[str]] = None,
        reference_embeddings: Optional[np.ndarray] = None,
        current_embeddings: Optional[np.ndarray] = None,
        reference_topics: Optional[List[int]] = None,
        current_topics: Optional[List[int]] = None,
        num_topics: int = 0,
    ) -> Dict[str, Any]:
        """run all applicable drift checks and return a combined report.
        drift is detected if ANY signal exceeds its threshold."""
        results = {}
        any_drifted = False

        if reference_docs is not None and current_docs is not None:
            vocab = self.detect_vocabulary_drift(reference_docs, current_docs)
            results["vocabulary"] = vocab
            if vocab["drifted"]:
                any_drifted = True

        if reference_embeddings is not None and current_embeddings is not None:
            emb = self.detect_embedding_drift(reference_embeddings, current_embeddings)
            results["embedding"] = emb
            if emb["drifted"]:
                any_drifted = True

        if reference_topics is not None and current_topics is not None:
            topic = self.detect_topic_drift(reference_topics, current_topics, num_topics)
            results["topic"] = topic
            if topic["drifted"]:
                any_drifted = True

        results["drift_detected"] = any_drifted
        return results

    # --- internal helpers ---

    @staticmethod
    def _word_frequencies(docs: List[str]) -> Dict[str, int]:
        """simple whitespace tokenizer + frequency counter."""
        freq: Dict[str, int] = {}
        for doc in docs:
            for word in doc.lower().split():
                # strip basic punctuation
                word = word.strip(".,!?;:\"'()[]{}—-–")
                if len(word) >= 2:
                    freq[word] = freq.get(word, 0) + 1
        return freq

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _jensen_shannon_divergence(p: np.ndarray, q: np.ndarray) -> float:
        """jensen-shannon divergence between two probability distributions.
        returns value in [0, 1] (using base-2 log)."""
        # add small epsilon to avoid log(0)
        eps = 1e-12
        p = p + eps
        q = q + eps
        p = p / p.sum()
        q = q / q.sum()
        m = 0.5 * (p + q)
        kl_pm = np.sum(p * np.log2(p / m))
        kl_qm = np.sum(q * np.log2(q / m))
        return float(0.5 * kl_pm + 0.5 * kl_qm)
