# tests for the topic_modeling module
# covers config, trainer, inference, validation, experiment_tracker
# all external dependencies (bertopic, umap, hdbscan, gemini, mlflow) are mocked

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "configs"))
sys.path.insert(0, str(Path(__file__).parent.parent))


# config tests

class TestTopicModelConfig:
    def test_default_config(self):
        with patch("config.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-key"
            mock_settings.GEMINI_MODEL = "gemini-test"
            mock_settings.EMBEDDING_MODEL = "test-model"

            from topic_modeling.config import TopicModelConfig
            cfg = TopicModelConfig()
            assert cfg.model_type == "journals"
            assert cfg.umap_n_neighbors == 15
            assert cfg.umap_n_components == 5
            assert cfg.umap_random_state == 42
            assert cfg.hdbscan_min_cluster_size == 10
            assert cfg.calculate_probabilities is True
            assert cfg.use_gemini_labels is True

    def test_config_to_dict_excludes_secrets(self):
        with patch("config.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "secret-key"
            mock_settings.GEMINI_MODEL = "gemini-test"
            mock_settings.EMBEDDING_MODEL = "test-model"

            from topic_modeling.config import TopicModelConfig
            cfg = TopicModelConfig()
            d = cfg.to_dict()
            assert "gemini_api_key" not in d
            assert "gemini_model" in d
            assert d["model_type"] == "journals"

    def test_conversation_config(self):
        with patch("config.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "key"
            mock_settings.GEMINI_MODEL = "model"
            mock_settings.EMBEDDING_MODEL = "embed"

            from topic_modeling.config import TopicModelConfig
            cfg = TopicModelConfig(model_type="conversations")
            assert cfg.model_type == "conversations"

    def test_hyperparameter_space(self):
        from topic_modeling.config import HyperparameterSpace
        space = HyperparameterSpace()
        assert len(space.umap_n_neighbors) == 3
        assert len(space.hdbscan_min_cluster_size) == 3
        assert 5 in space.umap_n_components

    def test_conversation_hyperparameter_space(self):
        from topic_modeling.config import ConversationHyperparameterSpace
        space = ConversationHyperparameterSpace()
        assert 20 in space.hdbscan_min_cluster_size
        assert 10 in space.umap_n_components

    def test_get_models_dir(self):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.config import get_models_dir
            journals_dir = get_models_dir("journals")
            assert "bertopic_journals" in str(journals_dir)

            conv_dir = get_models_dir("conversations")
            assert "bertopic_conversations" in str(conv_dir)

            sev_dir = get_models_dir("severity")
            assert "bertopic_severity" in str(sev_dir)

    def test_get_reports_dir(self):
        with patch("config.settings") as mock_settings:
            mock_settings.REPORTS_DIR = Path("/tmp/test/reports")

            from topic_modeling.config import get_reports_dir
            d = get_reports_dir()
            assert "model" in str(d)

    def test_get_mlruns_dir(self):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.config import get_mlruns_dir
            d = get_mlruns_dir()
            assert "mlruns" in str(d)

    def test_prompt_templates_have_placeholders(self):
        from topic_modeling.config import JOURNAL_LABEL_PROMPT, CONVERSATION_LABEL_PROMPT
        assert "[DOCUMENTS]" in JOURNAL_LABEL_PROMPT
        assert "[KEYWORDS]" in JOURNAL_LABEL_PROMPT
        assert "[DOCUMENTS]" in CONVERSATION_LABEL_PROMPT
        assert "[KEYWORDS]" in CONVERSATION_LABEL_PROMPT


# experiment tracker tests

class TestExperimentTracker:
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_setup_tracking(self, mock_set_exp, mock_set_uri):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test_experiment")
            assert tracker.experiment_name == "test_experiment"
            mock_set_exp.assert_called_once_with("test_experiment")

    @patch("mlflow.start_run")
    @patch("mlflow.log_param")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_start_run(self, mock_set_exp, mock_set_uri, mock_log_param, mock_start):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            mock_run = Mock()
            mock_run.info.run_id = "test-run-123"
            mock_start.return_value = mock_run

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            run_id = tracker.start_run("my_run", {"param1": "value1"})
            assert run_id == "test-run-123"
            mock_log_param.assert_called_once_with("param1", "value1")

    @patch("mlflow.log_metric")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_log_metrics(self, mock_set_exp, mock_set_uri, mock_log_metric):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            tracker.log_metrics({"score": 0.85, "loss": 0.15})
            assert mock_log_metric.call_count == 2

    @patch("mlflow.end_run")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_end_run(self, mock_set_exp, mock_set_uri, mock_end):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            tracker._run_id = "run-123"
            tracker.end_run()
            mock_end.assert_called_once()
            assert tracker.run_id is None

    @patch("mlflow.set_tag")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_tag_best_model(self, mock_set_exp, mock_set_uri, mock_set_tag):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            tracker._run_id = "run-123"
            tracker.tag_best_model()
            mock_set_tag.assert_called_with("model_status", "production")

    @patch("mlflow.get_experiment_by_name")
    @patch("mlflow.search_runs")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_best_run(self, mock_set_exp, mock_set_uri, mock_search, mock_get_exp):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            mock_exp = Mock()
            mock_exp.experiment_id = "exp-1"
            mock_get_exp.return_value = mock_exp

            mock_search.return_value = pd.DataFrame({
                "run_id": ["run-best"],
                "metrics.composite_score": [0.92],
                "params.model_type": ["journals"],
            })

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            best = tracker.get_best_run()
            assert best is not None
            assert best["run_id"] == "run-best"

    @patch("mlflow.get_experiment_by_name")
    @patch("mlflow.set_tracking_uri")
    @patch("mlflow.set_experiment")
    def test_get_best_run_no_experiment(self, mock_set_exp, mock_set_uri, mock_get_exp):
        with patch("config.settings") as mock_settings:
            mock_settings.PROJECT_ROOT = Path("/tmp/test")

            mock_get_exp.return_value = None

            from topic_modeling.experiment_tracker import ExperimentTracker
            tracker = ExperimentTracker("test")
            assert tracker.get_best_run() is None


# trainer tests

def _make_mock_bertopic(num_topics=5, num_docs=100):
    """create a mock bertopic model with realistic return values"""
    mock_model = MagicMock()

    # fit_transform returns topics and probabilities
    topics = list(np.random.choice(range(num_topics), size=num_docs, replace=True))
    topics[:5] = [-1] * 5  # some outliers
    probs = np.random.rand(num_docs, num_topics).astype(np.float32)

    mock_model.fit_transform.return_value = (topics, probs)
    mock_model.transform.return_value = (topics, probs)

    # topic info dataframe
    topic_info_data = {
        "Topic": list(range(-1, num_topics)),
        "Count": [5] + [int((num_docs - 5) / num_topics)] * num_topics,
        "Name": ["Outlier"] + [f"Topic_{i}" for i in range(num_topics)],
    }
    mock_model.get_topic_info.return_value = pd.DataFrame(topic_info_data)

    # get_topic returns word-weight pairs
    mock_model.get_topic.return_value = [
        (f"word_{i}", 0.1 - i * 0.01) for i in range(10)
    ]

    # outlier reduction
    mock_model.reduce_outliers.return_value = [0 if t == -1 else t for t in topics]
    mock_model.update_topics.return_value = None

    # topics over time
    mock_model.topics_over_time.return_value = pd.DataFrame({
        "Topic": [0, 1], "Words": ["word1", "word2"],
        "Frequency": [10, 8], "Timestamp": ["2025-01", "2025-02"],
    })

    # hierarchical topics
    mock_model.hierarchical_topics.return_value = pd.DataFrame({
        "Parent_ID": [0], "Parent_Name": ["parent"],
        "Topics": [[0, 1]], "Child_Left_ID": [0], "Child_Right_ID": [1],
    })

    mock_model.save = MagicMock()

    return mock_model


class TestTopicModelTrainer:
    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_init_default_config(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer
        trainer = TopicModelTrainer()
        assert trainer.config.model_type == "journals"

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_prepare_journal_docs(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"

        from topic_modeling.trainer import TopicModelTrainer
        df = pd.DataFrame({
            "content": ["entry 1", "entry 2"],
            "embedding_text": ["[2025-01-01] entry 1", "[2025-01-02] entry 2"],
            "entry_date": ["2025-01-01", "2025-01-02"],
        })
        docs, timestamps = TopicModelTrainer.prepare_journal_docs(df)
        assert len(docs) == 2
        assert timestamps is not None
        assert len(timestamps) == 2
        # prefers embedding_text
        assert docs[0].startswith("[2025-01-01]")

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_prepare_journal_docs_content_fallback(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"

        from topic_modeling.trainer import TopicModelTrainer
        df = pd.DataFrame({"content": ["entry 1", "entry 2"]})
        docs, timestamps = TopicModelTrainer.prepare_journal_docs(df)
        assert docs == ["entry 1", "entry 2"]
        assert timestamps is None

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_prepare_conversation_docs(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"

        from topic_modeling.trainer import TopicModelTrainer
        df = pd.DataFrame({
            "context": ["q1", "q2"],
            "embedding_text": ["User concern: q1\n\nCounselor response: a1", "User concern: q2\n\nCounselor response: a2"],
        })
        docs, timestamps = TopicModelTrainer.prepare_conversation_docs(df)
        assert len(docs) == 2
        assert timestamps is None
        assert "User concern" in docs[0]

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_prepare_journal_docs_missing_columns(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"

        from topic_modeling.trainer import TopicModelTrainer
        df = pd.DataFrame({"other_col": [1, 2]})
        with pytest.raises(ValueError, match="must have"):
            TopicModelTrainer.prepare_journal_docs(df)

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_compute_composite_score(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer
        trainer = TopicModelTrainer()

        result = {
            "num_topics": 10,
            "outlier_ratio": 0.05,
            "topic_info": [
                {"keywords": [f"word_{i}_{j}" for j in range(10)]}
                for i in range(10)
            ],
        }
        score = trainer._compute_composite_score(result)
        assert 0 <= score <= 1
        assert score > 0.5  # good result should score well

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_composite_score_zero_topics(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer
        trainer = TopicModelTrainer()
        score = trainer._compute_composite_score({"num_topics": 0, "outlier_ratio": 1.0, "topic_info": []})
        assert score == 0.0

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_serialize_topic_info(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer
        trainer = TopicModelTrainer()
        trainer.model = MagicMock()
        trainer.model.get_topic.return_value = [("word1", 0.5), ("word2", 0.3)]
        trainer.topic_info = pd.DataFrame({
            "Topic": [-1, 0, 1],
            "Count": [5, 40, 55],
            "Name": ["Outlier", "Topic_0", "Topic_1"],
            "llm": [None, "Anxiety and worry", "Depression and hopelessness"],
            "keybert": [None, "anxious worry", "depressed hopeless"],
        })

        result = trainer._serialize_topic_info()
        assert len(result) == 2  # excludes -1
        assert result[0]["topic_id"] == 0
        assert result[0]["llm_label"] == "Anxiety and worry"
        assert "keywords" in result[0]

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_train_basic(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = ""
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"

        mock_tracker = MagicMock()
        mock_tracker.run_id = "test-run-id"
        mock_tracker_cls.return_value = mock_tracker

        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig

        cfg = TopicModelConfig(use_gemini_labels=False)
        trainer = TopicModelTrainer(cfg)

        # mock the internal _build_bertopic to avoid umap/hdbscan import
        mock_bert_model = _make_mock_bertopic(num_topics=5, num_docs=50)
        trainer._build_bertopic = MagicMock(return_value=mock_bert_model)

        embeddings = np.random.rand(50, 384).astype(np.float32)
        docs = [f"document {i}" for i in range(50)]

        result = trainer.train(docs, embeddings=embeddings)

        assert result["model_type"] == "journals"
        assert result["num_topics"] == 5
        assert result["num_documents"] == 50
        assert "training_duration_seconds" in result
        assert result["mlflow_run_id"] == "test-run-id"
        mock_tracker.start_run.assert_called_once()
        mock_tracker.end_run.assert_called_once()

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_save_model(self, mock_settings, mock_tracker_cls):
        mock_settings.GEMINI_API_KEY = ""
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        mock_tracker = MagicMock()
        mock_tracker_cls.return_value = mock_tracker

        from topic_modeling.trainer import TopicModelTrainer
        from topic_modeling.config import TopicModelConfig

        cfg = TopicModelConfig(use_gemini_labels=False)
        trainer = TopicModelTrainer(cfg)
        trainer.model = MagicMock()

        with patch("topic_modeling.trainer.get_models_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/test/models/bertopic_journals/latest")
            path = trainer.save_model()
            trainer.model.save.assert_called_once()

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_patch_langchain_compat(self, mock_settings, mock_tracker_cls):
        """patch creates langchain.docstore.document shim when missing"""
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer
        import sys

        # remove any existing shim so we can test the patch
        for mod_name in list(sys.modules.keys()):
            if "langchain.docstore" in mod_name:
                del sys.modules[mod_name]

        # mock langchain and langchain_core imports
        mock_langchain = MagicMock()
        del mock_langchain.docstore  # simulate missing docstore

        mock_document = MagicMock()

        with patch.dict(sys.modules, {
            "langchain": mock_langchain,
            "langchain_core": MagicMock(),
            "langchain_core.documents": MagicMock(Document=mock_document),
        }):
            # clear any cached shim
            sys.modules.pop("langchain.docstore", None)
            sys.modules.pop("langchain.docstore.document", None)

            TopicModelTrainer._patch_langchain_compat()

            # verify shim was created
            assert "langchain.docstore" in sys.modules
            assert "langchain.docstore.document" in sys.modules
            assert sys.modules["langchain.docstore.document"].Document is mock_document

        # cleanup
        sys.modules.pop("langchain.docstore", None)
        sys.modules.pop("langchain.docstore.document", None)

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_make_qa_chain(self, mock_settings, mock_tracker_cls):
        """qa chain wraps llm to accept input_documents + question, return output_text"""
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "topic: Sleep Difficulties"
        mock_llm.invoke.return_value = mock_response

        chain = TopicModelTrainer._make_qa_chain(mock_llm)

        # create mock documents
        doc1 = MagicMock()
        doc1.page_content = "I couldn't sleep last night"
        doc2 = MagicMock()
        doc2.page_content = "Insomnia has been terrible"

        result = chain.invoke({
            "input_documents": [doc1, doc2],
            "question": "Documents:\n[DOCUMENTS]\nKeywords: sleep, insomnia\nLabel:",
        })

        assert result["output_text"] == "topic: Sleep Difficulties"
        mock_llm.invoke.assert_called_once()
        # verify [DOCUMENTS] was replaced with actual content
        call_args = mock_llm.invoke.call_args[0][0]
        assert "I couldn't sleep last night" in call_args
        assert "Insomnia has been terrible" in call_args
        assert "[DOCUMENTS]" not in call_args

    @patch("topic_modeling.trainer.ExperimentTracker")
    @patch("config.settings")
    def test_make_qa_chain_no_documents_placeholder(self, mock_settings, mock_tracker_cls):
        """qa chain appends docs to prompt when no [DOCUMENTS] placeholder"""
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "model"
        mock_settings.EMBEDDING_MODEL = "embed"
        mock_tracker_cls.return_value = MagicMock()

        from topic_modeling.trainer import TopicModelTrainer

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "topic: Anxiety"
        mock_llm.invoke.return_value = mock_response

        chain = TopicModelTrainer._make_qa_chain(mock_llm)

        doc = MagicMock()
        doc.page_content = "I feel anxious all day"

        result = chain.invoke({
            "input_documents": [doc],
            "question": "What is this about?",
        })

        assert result["output_text"] == "topic: Anxiety"
        call_args = mock_llm.invoke.call_args[0][0]
        assert "I feel anxious all day" in call_args
        assert "What is this about?" in call_args


# inference tests

class TestTopicModelInference:
    @patch("config.settings")
    def test_init(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        assert inf.model_type == "journals"
        assert not inf.is_loaded

    @patch("bertopic.BERTopic")
    @patch("config.settings")
    def test_load_success(self, mock_settings, mock_bt):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        mock_bt.load.return_value = MagicMock()

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")

        with patch("topic_modeling.inference.get_models_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.exists.return_value = True
            mock_dir.return_value = mock_path

            result = inf.load()
            assert result is True
            assert inf.is_loaded

    @patch("config.settings")
    def test_load_missing_model(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        result = inf.load(Path("/nonexistent/path"))
        assert result is False
        assert not inf.is_loaded

    @patch("config.settings")
    def test_predict_not_loaded(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        with pytest.raises(RuntimeError, match="not loaded"):
            inf.predict(["test doc"])

    @patch("config.settings")
    def test_predict(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.transform.return_value = ([0, 1, 0], np.array([[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]]))

        topics, probs = inf.predict(["doc1", "doc2", "doc3"])
        assert topics == [0, 1, 0]
        assert probs is not None

    @patch("config.settings")
    def test_predict_single(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.transform.return_value = ([2], np.array([[0.1, 0.2, 0.7]]))
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0, 1, 2], "Count": [10, 20, 30],
            "Name": ["T0", "T1", "T2"],
            "llm": ["Anxiety", "Depression", "Work stress"],
        })
        inf.model.get_topic.return_value = [("stress", 0.5), ("work", 0.3)]

        result = inf.predict_single("feeling stressed about work")
        assert result["topic_id"] == 2
        assert result["label"] == "Work stress"
        assert "probability" in result

    @patch("config.settings")
    def test_get_topic_label_prefers_llm(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        # bertopic stores multi-aspect representations as lists
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0], "Count": [10], "Name": ["0_anxiety_worry"],
            "llm": [["topic: Nighttime Anxiety Patterns", "", "", "", ""]],
            "keybert": [["anxious worried"]],
        })

        label = inf.get_topic_label(0)
        assert label == "Nighttime Anxiety Patterns"

    @patch("config.settings")
    def test_get_topic_label_llm_plain_string(self, mock_settings):
        """llm label can also be a plain string (not list)"""
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0], "Count": [10], "Name": ["0_anxiety_worry"],
            "llm": ["topic: Sleep Difficulties"], "keybert": ["sleep rest"],
        })

        label = inf.get_topic_label(0)
        assert label == "Sleep Difficulties"

    @patch("config.settings")
    def test_get_topic_label_fallback_keybert(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0], "Count": [10], "Name": ["0_anxiety_worry"],
            "llm": [["", "", ""]], "keybert": [["anxious worried"]],
        })

        label = inf.get_topic_label(0)
        assert label == "anxious worried"

    @patch("config.settings")
    def test_extract_label_list(self, mock_settings):
        """_extract_label handles list with first non-empty element"""
        from topic_modeling.inference import TopicModelInference
        assert TopicModelInference._extract_label(["topic: Sleep Quality", "", ""]) == "Sleep Quality"

    @patch("config.settings")
    def test_extract_label_empty_list(self, mock_settings):
        """_extract_label returns empty for all-empty list"""
        from topic_modeling.inference import TopicModelInference
        assert TopicModelInference._extract_label(["", "", ""]) == ""
        assert TopicModelInference._extract_label([]) == ""

    @patch("config.settings")
    def test_extract_label_plain_string(self, mock_settings):
        """_extract_label strips topic: prefix from plain strings"""
        from topic_modeling.inference import TopicModelInference
        assert TopicModelInference._extract_label("topic: Grief and Loss") == "Grief and Loss"
        assert TopicModelInference._extract_label("No prefix here") == "No prefix here"

    @patch("config.settings")
    def test_get_topic_label_outlier(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        assert inf.get_topic_label(-1) == "Outlier"

    @patch("config.settings")
    def test_get_topic_label_missing_topic(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0], "Count": [10], "Name": ["0_anxiety"],
        })

        assert inf.get_topic_label(999) == "Topic 999"

    @patch("config.settings")
    def test_get_all_topic_info(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [-1, 0, 1], "Count": [5, 40, 55],
            "Name": ["Outlier", "T0", "T1"],
            "llm": [None, "Anxiety", "Depression"],
        })
        inf.model.get_topic.return_value = [("word1", 0.5)]

        info = inf.get_all_topic_info()
        assert len(info) == 2  # excludes -1
        assert info[0]["topic_id"] == 0
        assert info[0]["label"] == "Anxiety"

    @patch("config.settings")
    def test_get_topic_distribution(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0, 1], "Count": [60, 40],
            "Name": ["T0", "T1"], "llm": ["Anxiety", "Depression"],
        })
        inf.model.get_topic.return_value = [("word1", 0.5)]

        dist = inf.get_topic_distribution([0, 0, 0, 1, 1, -1])
        assert len(dist) == 2
        assert dist[0]["topic_id"] == 0
        assert dist[0]["count"] == 3
        assert dist[0]["percentage"] == 60.0

    @patch("config.settings")
    def test_classify_with_distribution(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("journals")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.transform.return_value = ([0, 1], np.array([[0.8, 0.2], [0.3, 0.7]]))
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0, 1], "Count": [50, 50],
            "Name": ["T0", "T1"], "llm": ["Anxiety", "Depression"],
        })
        inf.model.get_topic.return_value = [("word1", 0.5)]

        results = inf.classify_with_distribution(["doc1", "doc2"])
        assert len(results) == 2
        assert results[0]["label"] == "Anxiety"
        assert results[1]["label"] == "Depression"

    @patch("config.settings")
    def test_topic_to_severity_maps_known_levels(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("severity")
        inf._loaded = True
        inf.model = MagicMock()

        # mock get_topic_label to return severity-named labels
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0, 1, 2, 3], "Count": [10, 10, 10, 10],
            "Name": ["T0", "T1", "T2", "T3"],
            "llm": ["Crisis - Suicidal Ideation", "Severe Distress", "Moderate Concern", "Mild Worry"],
        })

        assert inf._topic_to_severity(0) == "crisis"
        assert inf._topic_to_severity(1) == "severe"
        assert inf._topic_to_severity(2) == "moderate"
        assert inf._topic_to_severity(3) == "mild"

    @patch("config.settings")
    def test_topic_to_severity_outlier_is_unknown(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("severity")
        inf._loaded = True
        assert inf._topic_to_severity(-1) == "unknown"

    @patch("config.settings")
    def test_predict_severity(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("severity")
        inf._loaded = True
        inf.model = MagicMock()
        inf.model.transform.return_value = ([0, 1, -1], np.array([[0.9, 0.1], [0.3, 0.7], [0.0, 0.0]]))
        inf.model.get_topic_info.return_value = pd.DataFrame({
            "Topic": [0, 1], "Count": [50, 50],
            "Name": ["T0", "T1"],
            "llm": ["Crisis Level", "Mild Concern"],
        })

        result = inf.predict_severity(["doc1", "doc2", "doc3"])
        assert result == ["crisis", "mild", "unknown"]

    @patch("config.settings")
    def test_predict_severity_not_loaded(self, mock_settings):
        mock_settings.PROJECT_ROOT = Path("/tmp/test")

        from topic_modeling.inference import TopicModelInference
        inf = TopicModelInference("severity")
        with pytest.raises(RuntimeError, match="not loaded"):
            inf.predict_severity(["test"])


# validation tests

class TestTopicModelValidator:
    @patch("config.settings")
    def test_validate_passing(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        result = {
            "model_type": "journals",
            "num_topics": 10,
            "num_documents": 500,
            "outlier_ratio": 0.05,
            "outlier_count": 25,
            "topic_info": [
                {"topic_id": i, "count": 48, "keywords": [f"word_{i}_{j}" for j in range(10)],
                 "llm_label": f"Topic {i} label"}
                for i in range(10)
            ],
        }

        report = validator.validate(result)
        assert report["status"] == "pass"
        assert all(c["passed"] for c in report["checks"])
        assert report["metrics"]["composite_score"] > 0

    @patch("config.settings")
    def test_validate_failing_outliers(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        result = {
            "model_type": "journals",
            "num_topics": 10,
            "num_documents": 100,
            "outlier_ratio": 0.30,
            "outlier_count": 30,
            "topic_info": [
                {"topic_id": i, "count": 7, "keywords": [f"w{j}" for j in range(5)]}
                for i in range(10)
            ],
        }

        report = validator.validate(result)
        assert report["status"] == "fail"
        outlier_check = next(c for c in report["checks"] if c["name"] == "outlier_ratio")
        assert not outlier_check["passed"]

    @patch("config.settings")
    def test_validate_too_few_topics(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        result = {
            "model_type": "journals",
            "num_topics": 1,
            "num_documents": 100,
            "outlier_ratio": 0.50,
            "outlier_count": 50,
            "topic_info": [{"topic_id": 0, "count": 50, "keywords": ["word"]}],
        }

        report = validator.validate(result)
        assert report["status"] == "fail"

    @patch("config.settings")
    def test_topic_diversity_metric(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        # all unique keywords → high diversity
        high_div = validator._compute_topic_diversity([
            {"keywords": ["a", "b"]},
            {"keywords": ["c", "d"]},
        ])
        assert high_div == 1.0

        # overlapping keywords → lower diversity
        low_div = validator._compute_topic_diversity([
            {"keywords": ["a", "b"]},
            {"keywords": ["a", "b"]},
        ])
        assert low_div == 0.5

    @patch("config.settings")
    def test_size_gini(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        # perfectly balanced → gini ≈ 0
        balanced = validator._compute_size_gini([
            {"count": 50}, {"count": 50}, {"count": 50}
        ])
        assert balanced < 0.1

        # very imbalanced → higher gini
        imbalanced = validator._compute_size_gini([
            {"count": 1}, {"count": 1}, {"count": 98}
        ])
        assert imbalanced > 0.5

    @patch("config.settings")
    def test_label_quality(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        quality = validator._compute_label_quality([
            {"llm_label": "Anxiety and worry"},
            {"llm_label": "Depression"},
            {"llm_label": "Work stress"},
        ])
        assert quality["unique_ratio"] == 1.0
        assert quality["non_empty_ratio"] == 1.0

    @patch("config.settings")
    def test_save_report(self, mock_settings, tmp_path):
        mock_settings.REPORTS_DIR = tmp_path / "reports"

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        report = {"model_type": "journals", "status": "pass", "metrics": {}}

        with patch("topic_modeling.validation.get_reports_dir", return_value=tmp_path):
            path = validator.save_report(report)
            assert path.exists()

    @patch("config.settings")
    def test_empty_topic_info(self, mock_settings):
        mock_settings.REPORTS_DIR = Path("/tmp/reports")

        from topic_modeling.validation import TopicModelValidator
        validator = TopicModelValidator()

        assert validator._compute_topic_diversity([]) == 0.0
        assert validator._compute_avg_topic_size([]) == 0.0
        assert validator._compute_size_gini([]) == 0.0


# bias analysis tests are in test_topic_bias.py
