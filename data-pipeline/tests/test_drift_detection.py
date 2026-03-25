# tests for the data drift detection module
# verifies vocabulary drift, embedding drift, topic drift, and combined checks

import sys
from pathlib import Path

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))

from monitoring.drift_detector import DriftDetector
from conftest import FAKE_DIM


@pytest.fixture
def detector():
    return DriftDetector(
        vocab_threshold=0.65,
        embedding_threshold=0.30,
        topic_threshold=0.25,
    )


class TestVocabularyDrift:
    def test_no_drift_identical_docs(self, detector):
        docs = ["feeling anxious about work", "therapy session was helpful", "sleep has improved"]
        result = detector.detect_vocabulary_drift(docs, docs)
        assert result["similarity"] > 0.99
        assert result["drifted"] is False

    def test_drift_different_docs(self, detector):
        ref_docs = ["feeling anxious about work"] * 50
        cur_docs = ["database migration kubernetes deployment"] * 50
        result = detector.detect_vocabulary_drift(ref_docs, cur_docs)
        assert result["similarity"] < 0.65
        assert result["drifted"] is True

    def test_partial_overlap(self, detector):
        ref_docs = ["anxiety stress depression therapy"] * 30
        cur_docs = ["anxiety stress new topic emerging"] * 30
        result = detector.detect_vocabulary_drift(ref_docs, cur_docs)
        assert 0.0 < result["similarity"] < 1.0
        assert "new_words_ratio" in result

    def test_empty_reference(self, detector):
        result = detector.detect_vocabulary_drift([], ["some docs here"])
        assert result["drifted"] is False
        assert result["similarity"] == 1.0

    def test_empty_current(self, detector):
        result = detector.detect_vocabulary_drift(["some docs here"], [])
        assert result["drifted"] is False

    def test_vocab_size_reported(self, detector):
        ref = ["word1 word2 word3"] * 10
        cur = ["word1 word4 word5"] * 10
        result = detector.detect_vocabulary_drift(ref, cur)
        assert result["vocab_size"] > 0

    def test_new_words_ratio(self, detector):
        ref = ["alpha beta gamma"] * 20
        cur = ["delta epsilon zeta"] * 20
        result = detector.detect_vocabulary_drift(ref, cur)
        assert result["new_words_ratio"] > 0.0


class TestEmbeddingDrift:
    def test_no_drift_same_embeddings(self, detector):
        embeddings = np.random.randn(50, FAKE_DIM).astype(np.float32)
        result = detector.detect_embedding_drift(embeddings, embeddings)
        assert result["centroid_distance"] < 0.01
        assert result["drifted"] is False

    def test_drift_shifted_embeddings(self, detector):
        ref = np.random.randn(50, FAKE_DIM).astype(np.float32)
        # shift current embeddings significantly
        cur = ref + 5.0
        result = detector.detect_embedding_drift(ref, cur)
        assert result["drifted"] is True
        assert result["centroid_distance"] > 0.0

    def test_spread_ratio_reported(self, detector):
        ref = np.random.randn(50, FAKE_DIM).astype(np.float32)
        cur = np.random.randn(50, FAKE_DIM).astype(np.float32) * 3.0  # wider spread
        result = detector.detect_embedding_drift(ref, cur)
        assert "spread_ratio" in result
        assert result["spread_ratio"] > 1.0

    def test_empty_reference_embeddings(self, detector):
        empty = np.array([]).reshape(0, FAKE_DIM)
        cur = np.random.randn(10, FAKE_DIM).astype(np.float32)
        result = detector.detect_embedding_drift(empty, cur)
        assert result["drifted"] is False
        assert result["reason"] == "insufficient embeddings"

    def test_empty_current_embeddings(self, detector):
        ref = np.random.randn(10, FAKE_DIM).astype(np.float32)
        empty = np.array([]).reshape(0, FAKE_DIM)
        result = detector.detect_embedding_drift(ref, empty)
        assert result["drifted"] is False

    def test_similar_embeddings_no_drift(self, detector):
        rng = np.random.default_rng(42)
        ref = rng.standard_normal((100, FAKE_DIM)).astype(np.float32)
        # add small noise — should not drift
        cur = ref + rng.standard_normal((100, FAKE_DIM)).astype(np.float32) * 0.01
        result = detector.detect_embedding_drift(ref, cur)
        assert result["drifted"] is False


class TestTopicDrift:
    def test_no_drift_same_topics(self, detector):
        topics = [0, 1, 2, 3, 0, 1, 2, 3] * 10
        result = detector.detect_topic_drift(topics, topics, num_topics=4)
        assert result["jsd"] < 0.01
        assert result["drifted"] is False

    def test_drift_different_distributions(self, detector):
        ref_topics = [0] * 50 + [1] * 50
        cur_topics = [2] * 50 + [3] * 50
        result = detector.detect_topic_drift(ref_topics, cur_topics, num_topics=4)
        assert result["jsd"] > 0.25
        assert result["drifted"] is True

    def test_novel_topics_counted(self, detector):
        ref = [0, 1, 2] * 20
        cur = [0, 1, 5, 6] * 15
        result = detector.detect_topic_drift(ref, cur, num_topics=7)
        assert result["novel_topics"] == 2  # topics 5 and 6 are new

    def test_outlier_topics_handled(self, detector):
        ref = [-1, 0, 1, 2] * 20
        cur = [-1, 0, 1, 2] * 20
        result = detector.detect_topic_drift(ref, cur, num_topics=3)
        assert result["drifted"] is False

    def test_empty_topics(self, detector):
        result = detector.detect_topic_drift([], [0, 1], num_topics=2)
        assert result["drifted"] is False
        assert result["reason"] == "insufficient topics"

    def test_ref_and_cur_topic_counts(self, detector):
        ref = [0, 1, 2] * 20
        cur = [0, 1, 2, 3, 4] * 12
        result = detector.detect_topic_drift(ref, cur, num_topics=5)
        assert result["ref_topic_count"] == 3
        assert result["cur_topic_count"] == 5


class TestCombinedDriftCheck:
    def test_no_drift_overall(self, detector):
        docs = ["therapy anxiety depression help"] * 30
        embeddings = np.random.randn(30, FAKE_DIM).astype(np.float32)
        topics = [0, 1, 2] * 10

        result = detector.run_drift_check(
            reference_docs=docs, current_docs=docs,
            reference_embeddings=embeddings, current_embeddings=embeddings,
            reference_topics=topics, current_topics=topics,
            num_topics=3,
        )
        assert result["drift_detected"] is False
        assert "vocabulary" in result
        assert "embedding" in result
        assert "topic" in result

    def test_vocab_drift_triggers_overall(self, detector):
        ref_docs = ["therapy anxiety depression"] * 50
        cur_docs = ["kubernetes docker deployment pipeline"] * 50

        result = detector.run_drift_check(
            reference_docs=ref_docs, current_docs=cur_docs,
        )
        assert result["drift_detected"] is True
        assert result["vocabulary"]["drifted"] is True

    def test_partial_checks(self, detector):
        """only vocab check runs when embeddings/topics not provided"""
        docs = ["therapy is helpful"] * 20
        result = detector.run_drift_check(
            reference_docs=docs, current_docs=docs,
        )
        assert result["drift_detected"] is False
        assert "vocabulary" in result
        assert "embedding" not in result
        assert "topic" not in result

    def test_no_inputs_no_drift(self, detector):
        result = detector.run_drift_check()
        assert result["drift_detected"] is False

    def test_any_signal_triggers_drift(self, detector):
        """drift is detected if ANY signal exceeds its threshold"""
        ref_docs = ["same text"] * 30
        ref_emb = np.random.randn(30, FAKE_DIM).astype(np.float32)
        cur_emb = ref_emb + 10.0  # big shift in embeddings

        result = detector.run_drift_check(
            reference_docs=ref_docs, current_docs=ref_docs,
            reference_embeddings=ref_emb, current_embeddings=cur_emb,
        )
        assert result["drift_detected"] is True
        assert result["vocabulary"]["drifted"] is False
        assert result["embedding"]["drifted"] is True


class TestHelperMethods:
    def test_word_frequencies(self):
        docs = ["hello world", "hello python world"]
        freq = DriftDetector._word_frequencies(docs)
        assert freq["hello"] == 2
        assert freq["world"] == 2
        assert freq["python"] == 1

    def test_word_frequencies_strips_punctuation(self):
        docs = ["hello, world! how's it going?"]
        freq = DriftDetector._word_frequencies(docs)
        assert "hello" in freq
        assert "world" in freq

    def test_word_frequencies_ignores_short(self):
        docs = ["I a am the good"]
        freq = DriftDetector._word_frequencies(docs)
        assert "I" not in freq  # single char
        assert "a" not in freq
        assert "am" in freq  # 2 chars is ok

    def test_cosine_similarity_identical(self):
        v = np.array([1.0, 2.0, 3.0])
        assert abs(DriftDetector._cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        assert abs(DriftDetector._cosine_similarity(v1, v2)) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        v1 = np.array([0.0, 0.0])
        v2 = np.array([1.0, 2.0])
        assert DriftDetector._cosine_similarity(v1, v2) == 0.0

    def test_jsd_identical_distributions(self):
        p = np.array([0.5, 0.3, 0.2])
        assert DriftDetector._jensen_shannon_divergence(p, p) < 0.001

    def test_jsd_different_distributions(self):
        p = np.array([1.0, 0.0, 0.0])
        q = np.array([0.0, 0.0, 1.0])
        jsd = DriftDetector._jensen_shannon_divergence(p, q)
        assert 0.0 < jsd <= 1.0

    def test_jsd_symmetry(self):
        p = np.array([0.7, 0.2, 0.1])
        q = np.array([0.3, 0.4, 0.3])
        assert abs(DriftDetector._jensen_shannon_divergence(p, q) -
                   DriftDetector._jensen_shannon_divergence(q, p)) < 1e-10
