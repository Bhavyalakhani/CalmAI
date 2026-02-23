# bertopic model trainer
# builds and trains topic models for journals and conversations
# uses multi-aspect representations: keybert + gemini llm + mmr
# pre-calculates embeddings for speed, deterministic umap for reproducibility

import logging
import time
import itertools
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .config import (
    TopicModelConfig,
    HyperparameterSpace,
    ConversationHyperparameterSpace,
    SeverityHyperparameterSpace,
    JOURNAL_LABEL_PROMPT,
    CONVERSATION_LABEL_PROMPT,
    SEVERITY_LABEL_PROMPT,
    get_models_dir,
)
from .experiment_tracker import ExperimentTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TopicModelTrainer:
    """trains bertopic models with multi-aspect gemini llm labeling"""

    def __init__(self, model_config: Optional[TopicModelConfig] = None):
        self.config = model_config or TopicModelConfig()
        self.model = None
        self.embeddings = None
        self.topics = None
        self.probs = None
        self.topic_info = None
        self.tracker = ExperimentTracker(
            experiment_name=f"{self.config.model_type}_topic_model"
        )

    # component builders

    def _build_umap(self):
        """build umap model with deterministic random state.
        umap-learn is a runtime dependency installed in the airflow docker container.
        lazy import avoids build failures in environments without c extensions.
        """
        from umap import UMAP  # type: ignore[import-untyped]
        return UMAP(
            n_neighbors=self.config.umap_n_neighbors,
            n_components=self.config.umap_n_components,
            min_dist=self.config.umap_min_dist,
            metric=self.config.umap_metric,
            random_state=self.config.umap_random_state,
        )

    def _build_hdbscan(self):
        """build hdbscan clustering model.
        uses standalone hdbscan package (compiles fine on linux/docker).
        prediction_data=True required for calculate_probabilities support.
        """
        from hdbscan import HDBSCAN  # type: ignore[import-untyped]
        return HDBSCAN(
            min_cluster_size=self.config.hdbscan_min_cluster_size,
            min_samples=self.config.hdbscan_min_samples,
            metric=self.config.hdbscan_metric,
            cluster_selection_method=self.config.hdbscan_cluster_selection_method,
            prediction_data=True,
        )

    def _build_vectorizer(self):
        """build count vectorizer for c-tf-idf"""
        from sklearn.feature_extraction.text import CountVectorizer
        return CountVectorizer(
            stop_words=self.config.vectorizer_stop_words,
            min_df=self.config.vectorizer_min_df,
            ngram_range=self.config.vectorizer_ngram_range,
        )

    def _build_representation_models(self) -> Dict[str, Any]:
        """build multi-aspect representation models:
        - keybert: keyword-based fallback (always works)
        - gemini: llm-generated clinically descriptive labels
        - mmr: diverse keyword representation
        """
        from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance

        representation_models = {
            "keybert": KeyBERTInspired(top_n_words=self.config.top_n_words),
            "mmr": MaximalMarginalRelevance(diversity=0.3),
        }

        if self.config.use_gemini_labels and self.config.gemini_api_key:
            try:
                # patch langchain.docstore.document for bertopic 0.17.x compat.
                # must run before importing _langchain module.
                self._patch_langchain_compat()

                # import from private module — the public `bertopic.representation`
                # caches a NotInstalled sentinel when the initial import fails during
                # `from bertopic import BERTopic`. importing from the private module
                # triggers a fresh load after the patch is in place.
                from bertopic.representation._langchain import LangChain
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(
                    model=self.config.gemini_model,
                    google_api_key=self.config.gemini_api_key,
                    temperature=0.1,
                )

                prompt = (
                    JOURNAL_LABEL_PROMPT
                    if self.config.model_type == "journals"
                    else SEVERITY_LABEL_PROMPT
                    if self.config.model_type == "severity"
                    else CONVERSATION_LABEL_PROMPT
                )

                # bertopic's langchain class expects a chain that accepts
                # {"input_documents": [...], "question": "..."} and returns
                # {"output_text": "..."}. a raw llm won't work — wrap it.
                chain = self._make_qa_chain(llm)

                representation_models["llm"] = LangChain(
                    chain,
                    prompt=prompt,
                    nr_docs=5,
                    diversity=0.1,
                )
                logger.info("Gemini LLM representation model configured")
            except Exception as e:
                logger.warning(f"Failed to configure Gemini LLM: {e}. Using keybert only.")

        return representation_models

    @staticmethod
    def _patch_langchain_compat():
        """patch langchain.docstore.document for bertopic 0.17.x compat with langchain 1.x.
        bertopic imports `from langchain.docstore.document import Document` at module level,
        but langchain 1.x removed that path. create a shim pointing to langchain_core.
        """
        try:
            from langchain.docstore.document import Document  # type: ignore # noqa: F401
            return  # already available, no patch needed
        except (ImportError, ModuleNotFoundError):
            pass

        import sys
        import types
        import langchain
        from langchain_core.documents import Document as LCDocument

        docstore_mod = types.ModuleType("langchain.docstore")
        docstore_doc_mod = types.ModuleType("langchain.docstore.document")
        docstore_doc_mod.Document = LCDocument
        docstore_mod.document = docstore_doc_mod

        langchain.docstore = docstore_mod
        sys.modules["langchain.docstore"] = docstore_mod
        sys.modules["langchain.docstore.document"] = docstore_doc_mod
        logger.info("Patched langchain.docstore.document for bertopic 0.17.x compat")

    @staticmethod
    def _make_qa_chain(llm):
        """create a qa chain compatible with bertopic's langchain representation.
        bertopic expects chain.batch([{"input_documents": [...], "question": "..."}])
        returning [{"output_text": "..."}]. a raw llm doesn't satisfy this interface,
        so we wrap it in a runnable that formats documents into the prompt.
        """
        from langchain_core.runnables import RunnableLambda

        def _invoke(input_dict: dict) -> dict:
            docs = input_dict.get("input_documents", [])
            question = input_dict.get("question", "")

            # format document contents
            doc_text = "\n".join(
                f"- {d.page_content}" for d in docs if hasattr(d, "page_content")
            )

            # replace [DOCUMENTS] placeholder if present in prompt
            if "[DOCUMENTS]" in question:
                full_prompt = question.replace("[DOCUMENTS]", doc_text)
            else:
                full_prompt = f"{doc_text}\n\n{question}"

            response = llm.invoke(full_prompt)
            output_text = response.content if hasattr(response, "content") else str(response)
            return {"output_text": output_text}

        return RunnableLambda(_invoke)

    def _build_bertopic(self):
        """assemble the full bertopic model from components"""
        from bertopic import BERTopic
        from sentence_transformers import SentenceTransformer

        umap_model = self._build_umap()
        hdbscan_model = self._build_hdbscan()
        vectorizer_model = self._build_vectorizer()
        representation_models = self._build_representation_models()

        embedding_model = SentenceTransformer(self.config.embedding_model_name)

        return BERTopic(
            embedding_model=embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            representation_model=representation_models,
            top_n_words=self.config.top_n_words,
            nr_topics=self.config.nr_topics,
            calculate_probabilities=self.config.calculate_probabilities,
            verbose=True,
        )

    # embedding helpers

    def _pre_calculate_embeddings(self, docs: List[str]) -> np.ndarray:
        """pre-calculate embeddings for all documents (bertopic best practice)"""
        from sentence_transformers import SentenceTransformer

        logger.info(f"Pre-calculating embeddings for {len(docs)} documents...")
        model = SentenceTransformer(self.config.embedding_model_name)
        embeddings = model.encode(docs, show_progress_bar=True, batch_size=64)
        logger.info(f"Embeddings shape: {embeddings.shape}")
        return embeddings

    # training

    def train(
        self,
        docs: List[str],
        embeddings: Optional[np.ndarray] = None,
        timestamps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """train a bertopic model on the provided documents.

        args:
            docs: list of text documents to cluster
            embeddings: pre-calculated embeddings (optional, computed if not provided)
            timestamps: list of date strings for topics_over_time (optional)

        returns:
            dict with training results (topics, metrics, model info)
        """
        start_time = time.time()
        run_name = f"{self.config.model_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # start mlflow tracking
        self.tracker.start_run(
            run_name=run_name,
            params=self.config.to_dict(),
        )

        try:
            # pre-calculate embeddings if not provided
            if embeddings is None:
                self.embeddings = self._pre_calculate_embeddings(docs)
            else:
                self.embeddings = embeddings
                logger.info(f"Using provided embeddings: {embeddings.shape}")

            # build and fit model
            logger.info(f"Building BERTopic model for {self.config.model_type}...")
            self.model = self._build_bertopic()

            logger.info(f"Fitting model on {len(docs)} documents...")
            self.topics, self.probs = self.model.fit_transform(docs, self.embeddings)

            # reduce outliers using c-tf-idf + distributions strategy chain
            self._reduce_outliers(docs)

            # get topic info
            self.topic_info = self.model.get_topic_info()
            num_topics = len(self.topic_info[self.topic_info["Topic"] != -1])
            outlier_count = int((np.array(self.topics) == -1).sum())
            outlier_ratio = outlier_count / len(docs) if docs else 0

            logger.info(f"Found {num_topics} topics, {outlier_count} outliers ({outlier_ratio:.1%})")

            # compute topics over time if timestamps provided
            topics_over_time = None
            if timestamps and len(timestamps) == len(docs):
                try:
                    topics_over_time = self.model.topics_over_time(
                        docs, timestamps, nr_bins=12
                    )
                    logger.info(f"Topics over time computed: {len(topics_over_time)} rows")
                except Exception as e:
                    logger.warning(f"Topics over time failed: {e}")

            # compute hierarchical topics
            hierarchical_topics = None
            try:
                hierarchical_topics = self.model.hierarchical_topics(docs)
                logger.info("Hierarchical topics computed")
            except Exception as e:
                logger.warning(f"Hierarchical topics failed: {e}")

            duration = time.time() - start_time

            # log metrics to mlflow
            metrics = {
                "num_topics": num_topics,
                "num_documents": len(docs),
                "outlier_count": outlier_count,
                "outlier_ratio": outlier_ratio,
                "training_duration_seconds": duration,
            }
            self.tracker.log_metrics(metrics)

            # build result
            result = {
                "model_type": self.config.model_type,
                "num_topics": num_topics,
                "num_documents": len(docs),
                "outlier_count": outlier_count,
                "outlier_ratio": round(outlier_ratio, 4),
                "topic_info": self._serialize_topic_info(),
                "topics_over_time": (
                    topics_over_time.to_dict(orient="records")
                    if topics_over_time is not None
                    else None
                ),
                "hierarchical_topics": (
                    hierarchical_topics.to_dict(orient="records")
                    if hierarchical_topics is not None
                    else None
                ),
                "training_duration_seconds": round(duration, 2),
                "config": self.config.to_dict(),
                "run_name": run_name,
                "mlflow_run_id": self.tracker.run_id,
            }

            logger.info(f"Training complete in {duration:.1f}s: {num_topics} topics from {len(docs)} docs")
            return result

        except Exception as e:
            logger.error(f"Training failed: {e}")
            self.tracker.set_tag("status", "failed")
            raise
        finally:
            self.tracker.end_run()

    def _reduce_outliers(self, docs: List[str]):
        """reduce outliers using a chain: c-tf-idf first, then distributions"""
        if self.model is None or self.topics is None:
            return

        initial_outliers = int((np.array(self.topics) == -1).sum())
        if initial_outliers == 0:
            return

        logger.info(f"Reducing outliers (initial: {initial_outliers})...")

        # strategy 1: c-tf-idf similarity
        try:
            new_topics = self.model.reduce_outliers(
                docs, self.topics, strategy="c-tf-idf", threshold=0.1
            )
            self.model.update_topics(docs, topics=new_topics)
            self.topics = new_topics
        except Exception as e:
            logger.warning(f"c-tf-idf outlier reduction failed: {e}")

        # strategy 2: distribution-based (if probabilities available)
        try:
            if self.probs is not None and len(self.probs.shape) > 1:
                new_topics = self.model.reduce_outliers(
                    docs, self.topics, strategy="distributions", threshold=0.05
                )
                self.model.update_topics(docs, topics=new_topics)
                self.topics = new_topics
        except Exception as e:
            logger.warning(f"Distribution outlier reduction failed: {e}")

        final_outliers = int((np.array(self.topics) == -1).sum())
        logger.info(f"Outliers reduced: {initial_outliers} -> {final_outliers}")

    def _serialize_topic_info(self) -> List[Dict[str, Any]]:
        """serialize topic info to json-safe format"""
        if self.topic_info is None:
            return []

        records = []
        for _, row in self.topic_info.iterrows():
            topic_id = int(row["Topic"])
            if topic_id == -1:
                continue

            record = {
                "topic_id": topic_id,
                "count": int(row["Count"]),
                "name": str(row.get("Name", "")),
            }

            # extract multi-aspect representations using inference's label extraction
            from .inference import TopicModelInference
            if "keybert" in row and row["keybert"] is not None:
                record["keybert_label"] = TopicModelInference._extract_label(row["keybert"]) or str(row["keybert"])
            if "llm" in row and row["llm"] is not None:
                record["llm_label"] = TopicModelInference._extract_label(row["llm"]) or str(row["llm"])
            if "mmr" in row and row["mmr"] is not None:
                record["mmr_label"] = TopicModelInference._extract_label(row["mmr"]) or str(row["mmr"])

            # extract representative words from default representation
            topic_words = self.model.get_topic(topic_id)
            if topic_words:
                record["keywords"] = [w for w, _ in topic_words[:10]]

            records.append(record)

        return records

    # save and load

    def save_model(self, path: Optional[Path] = None) -> Path:
        """save trained model using safetensors serialization"""
        if self.model is None:
            raise RuntimeError("No model to save. Train first.")

        save_dir = path or get_models_dir(self.config.model_type)
        save_dir.mkdir(parents=True, exist_ok=True)

        model_path = save_dir / "model"
        self.model.save(
            str(model_path),
            serialization="safetensors",
            save_ctfidf=True,
            save_embedding_model=self.config.embedding_model_name,
        )

        logger.info(f"Model saved to {model_path}")

        # log model directory as mlflow artifact
        try:
            self.tracker.log_artifacts_dir(str(model_path))
        except Exception as e:
            logger.warning(f"Failed to log model artifacts to MLflow: {e}")

        return model_path

    # hyperparameter tuning

    def tune(
        self,
        docs: List[str],
        embeddings: Optional[np.ndarray] = None,
        max_combinations: int = 20,
    ) -> Dict[str, Any]:
        """grid search over hyperparameter space to find best configuration.
        uses pre-calculated embeddings to speed up iterations.

        returns:
            dict with best config, best metrics, and all trial results
        """
        if embeddings is None:
            embeddings = self._pre_calculate_embeddings(docs)

        space = (
            HyperparameterSpace()
            if self.config.model_type == "journals"
            else SeverityHyperparameterSpace()
            if self.config.model_type == "severity"
            else ConversationHyperparameterSpace()
        )

        # generate all combinations
        param_names = [
            "umap_n_neighbors", "umap_n_components",
            "hdbscan_min_cluster_size", "hdbscan_min_samples",
            "top_n_words"
        ]
        param_values = [
            space.umap_n_neighbors, space.umap_n_components,
            space.hdbscan_min_cluster_size, space.hdbscan_min_samples,
            space.top_n_words,
        ]
        all_combos = list(itertools.product(*param_values))

        # limit combinations
        if len(all_combos) > max_combinations:
            rng = np.random.RandomState(42)
            indices = rng.choice(len(all_combos), max_combinations, replace=False)
            combos = [all_combos[i] for i in sorted(indices)]
        else:
            combos = all_combos

        logger.info(f"Tuning: {len(combos)} combinations from {len(all_combos)} total")

        trials = []
        best_score = -1
        best_trial = None

        for i, combo in enumerate(combos):
            params = dict(zip(param_names, combo))
            logger.info(f"Trial {i+1}/{len(combos)}: {params}")

            # create config for this trial (disable gemini to speed up tuning)
            trial_config = TopicModelConfig(
                model_type=self.config.model_type,
                umap_n_neighbors=params["umap_n_neighbors"],
                umap_n_components=params["umap_n_components"],
                hdbscan_min_cluster_size=params["hdbscan_min_cluster_size"],
                hdbscan_min_samples=params["hdbscan_min_samples"],
                top_n_words=params["top_n_words"],
                use_gemini_labels=False,  # skip llm during tuning for speed
            )

            trainer = TopicModelTrainer(trial_config)
            try:
                result = trainer.train(docs, embeddings=embeddings)
                score = self._compute_composite_score(result)
                result["composite_score"] = score

                trials.append({"params": params, "result": result, "score": score})

                if score > best_score:
                    best_score = score
                    best_trial = {"params": params, "result": result, "score": score}

                logger.info(f"  -> {result['num_topics']} topics, outlier_ratio={result['outlier_ratio']}, score={score:.3f}")

            except Exception as e:
                logger.warning(f"  Trial failed: {e}")
                trials.append({"params": params, "error": str(e), "score": 0})

        if best_trial:
            logger.info(f"Best trial: score={best_trial['score']:.3f}, params={best_trial['params']}")

        return {
            "best_trial": best_trial,
            "all_trials": trials,
            "num_trials": len(trials),
        }

    def _compute_composite_score(self, result: Dict[str, Any]) -> float:
        """compute a composite quality score for a training result.
        balances topic count, outlier ratio, and topic diversity.
        """
        num_topics = result.get("num_topics", 0)
        outlier_ratio = result.get("outlier_ratio", 1.0)
        topic_info = result.get("topic_info", [])

        if num_topics == 0:
            return 0.0

        # topic count score: prefer 5-25 topics, penalize outside
        if 5 <= num_topics <= 25:
            topic_score = 1.0
        elif num_topics < 5:
            topic_score = num_topics / 5
        else:
            topic_score = max(0, 1.0 - (num_topics - 25) / 25)

        # outlier score: lower is better
        outlier_score = max(0, 1.0 - outlier_ratio * 5)

        # diversity score: based on unique keywords across topics
        all_keywords = set()
        for t in topic_info:
            all_keywords.update(t.get("keywords", []))
        total_possible = num_topics * 10
        diversity_score = len(all_keywords) / total_possible if total_possible > 0 else 0

        # weighted composite
        score = (topic_score * 0.4) + (outlier_score * 0.4) + (diversity_score * 0.2)
        return round(score, 4)

    # data preparation helpers

    @staticmethod
    def prepare_journal_docs(df: pd.DataFrame) -> Tuple[List[str], Optional[List[str]]]:
        """extract documents and timestamps from a journal dataframe.
        uses 'embedding_text' if available, otherwise 'content'.
        """
        if "embedding_text" in df.columns:
            docs = df["embedding_text"].astype(str).tolist()
        elif "content" in df.columns:
            docs = df["content"].astype(str).tolist()
        else:
            raise ValueError("DataFrame must have 'embedding_text' or 'content' column")

        timestamps = None
        if "entry_date" in df.columns:
            timestamps = pd.to_datetime(df["entry_date"], errors="coerce").dt.strftime("%Y-%m-%d").tolist()

        return docs, timestamps

    @staticmethod
    def prepare_conversation_docs(df: pd.DataFrame) -> Tuple[List[str], None]:
        """extract documents from a conversation dataframe.
        uses 'embedding_text' if available, otherwise 'context'.
        """
        if "embedding_text" in df.columns:
            docs = df["embedding_text"].astype(str).tolist()
        elif "context" in df.columns:
            docs = df["context"].astype(str).tolist()
        else:
            raise ValueError("DataFrame must have 'embedding_text' or 'context' column")

        return docs, None
