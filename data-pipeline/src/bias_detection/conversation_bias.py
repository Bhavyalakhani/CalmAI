# bias analysis for the conversations dataset
# classifies topics (10 categories) and severity (4 levels),
# finds underrepresented topics, cross-analyzes response length,
# detects topic overlap, and generates visualizations + mitigation notes

import json
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config

from .slicer import DataSlicer, SliceStats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BiasReport:
    dataset_name: str
    timestamp: str
    total_records: int
    topic_distribution: Dict[str, Dict[str, Any]]
    severity_distribution: Dict[str, Dict[str, Any]]
    underrepresented_topics: List[str]
    cross_analysis: Dict[str, Any]
    topic_overlap: Dict[str, Any]
    mitigation_notes: List[str]


class ConversationBiasAnalyzer:
    
    # 10 mental health topics with keyword lists
    TOPICS = {
        "anxiety": ["anxious", "anxiety", "worry", "worried", "panic", "nervous", "fear"],
        "depression": ["depressed", "depression", "hopeless", "sad", "empty", "worthless", "numb"],
        "relationships": ["relationship", "partner", "boyfriend", "girlfriend", "spouse", "marriage", "dating"],
        "family": ["family", "parent", "mother", "father", "sibling", "brother", "sister", "child"],
        "work": ["work", "job", "career", "boss", "colleague", "coworker", "workplace", "fired"],
        "trauma": ["trauma", "ptsd", "abuse", "assault", "violence", "accident"],
        "self_harm": ["self-harm", "cutting", "suicide", "suicidal", "hurt myself", "end my life"],
        "substance": ["alcohol", "drug", "addiction", "drinking", "substance", "sober", "relapse"],
        "grief": ["grief", "loss", "death", "died", "mourning", "funeral", "passed away"],
        "identity": ["identity", "gender", "sexuality", "lgbtq", "transgender", "coming out"]
    }
    
    # 4 severity levels — applied from mild to crisis so highest wins
    SEVERITY = {
        "crisis": ["suicide", "kill myself", "emergency", "crisis", "can't go on", "end it all"],
        "severe": ["can't cope", "unbearable", "desperate", "breaking down", "falling apart"],
        "moderate": ["struggling", "difficult", "hard time", "overwhelmed", "stressed"],
        "mild": ["sometimes", "occasionally", "minor", "a little", "slightly"]
    }
    
    # topics below this % are flagged as underrepresented
    UNDERREPRESENTATION_THRESHOLD = 3.0
    
    def __init__(self):
        self.settings = config.settings
        self.df = None
        self.slicer = None
    
    def get_input_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "conversations" / "processed_conversations.parquet"
    
    def get_reports_dir(self) -> Path:
        reports_dir = self.settings.REPORTS_DIR / "bias"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir
    
    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Processed conversations not found: {input_path}")
        
        self.df = pd.read_parquet(input_path)
        self.slicer = DataSlicer(self.df)
        logger.info(f"Loaded {len(self.df)} conversations for bias analysis")
        return self.df
    
    # classification

    def classify_topics(self) -> pd.DataFrame:
        for topic, keywords in self.TOPICS.items():
            pattern = "|".join(keywords)
            self.df[f"topic_{topic}"] = self.df["context"].str.contains(
                pattern, case=False, na=False
            )
        return self.df
    
    # applied mild -> moderate -> severe -> crisis so highest severity wins
    def classify_severity(self) -> pd.DataFrame:
        self.df["severity"] = "unknown"

        # last match wins (highest severity takes priority)
        for severity in ["mild", "moderate", "severe", "crisis"]:
            keywords = self.SEVERITY[severity]
            pattern = "|".join(keywords)
            mask = self.df["context"].str.contains(pattern, case=False, na=False)
            self.df.loc[mask, "severity"] = severity
        
        return self.df
    
    # analysis

    def analyze_topic_distribution(self) -> Dict[str, Dict[str, Any]]:
        topic_stats = {}
        total = len(self.df)
        
        for topic in self.TOPICS.keys():
            col = f"topic_{topic}"
            if col not in self.df.columns:
                continue
            
            topic_df = self.df[self.df[col]]
            count = len(topic_df)
            percentage = (count / total * 100) if total > 0 else 0
            
            response_length_mean = 0
            if "response_word_count" in topic_df.columns and count > 0:
                response_length_mean = float(topic_df["response_word_count"].mean())
            
            topic_stats[topic] = {
                "count": count,
                "percentage": round(percentage, 2),
                "response_length_mean": round(response_length_mean, 2)
            }
        
        return topic_stats
    
    def analyze_severity_distribution(self) -> Dict[str, Dict[str, Any]]:
        slicer = DataSlicer(self.df)
        severity_slices = slicer.slice_by_category("severity")
        severity_stats = {}
        total = len(self.df)
        
        for severity in list(self.SEVERITY.keys()) + ["unknown"]:
            severity_df = severity_slices.get(severity, pd.DataFrame())
            count = len(severity_df)
            percentage = (count / total * 100) if total > 0 else 0
            
            response_length_mean = 0
            if "response_word_count" in severity_df.columns and count > 0:
                response_length_mean = float(severity_df["response_word_count"].mean())
            
            severity_stats[severity] = {
                "count": count,
                "percentage": round(percentage, 2),
                "response_length_mean": round(response_length_mean, 2)
            }
        
        return severity_stats
    
    def find_underrepresented_topics(self, topic_stats: Dict[str, Dict[str, Any]]) -> List[str]:
        underrepresented = []
        for topic, stats in topic_stats.items():
            if stats["percentage"] < self.UNDERREPRESENTATION_THRESHOLD:
                underrepresented.append(topic)
        return underrepresented
    
    # checks which topics get noticeably shorter/longer responses
    def cross_analyze(self, topic_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        overall_response_mean = 0
        if "response_word_count" in self.df.columns:
            overall_response_mean = float(self.df["response_word_count"].mean())
        
        shorter_response_topics = []
        longer_response_topics = []
        
        for topic, stats in topic_stats.items():
            if stats["count"] < 10:
                continue
            
            diff = stats["response_length_mean"] - overall_response_mean
            if diff < -20:
                shorter_response_topics.append({
                    "topic": topic,
                    "response_mean": stats["response_length_mean"],
                    "diff_from_overall": round(diff, 2)
                })
            elif diff > 20:
                longer_response_topics.append({
                    "topic": topic,
                    "response_mean": stats["response_length_mean"],
                    "diff_from_overall": round(diff, 2)
                })
        
        return {
            "overall_response_mean": round(overall_response_mean, 2),
            "shorter_response_topics": shorter_response_topics,
            "longer_response_topics": longer_response_topics
        }
    
    # how many conversations match >1 topic, and top co-occurring pairs
    def analyze_topic_overlap(self) -> Dict[str, Any]:
        topic_cols = [f"topic_{t}" for t in self.TOPICS if f"topic_{t}" in self.df.columns]
        
        if not topic_cols:
            return {}
        
        topic_counts = self.df[topic_cols].sum(axis=1)
        
        multi_topic = int((topic_counts > 1).sum())
        no_topic = int((topic_counts == 0).sum())
        total = len(self.df)
        
        # Top co-occurring topic pairs
        co_occurrences = {}
        topic_names = list(self.TOPICS.keys())
        for i, t1 in enumerate(topic_names):
            for t2 in topic_names[i + 1:]:
                col1, col2 = f"topic_{t1}", f"topic_{t2}"
                if col1 in self.df.columns and col2 in self.df.columns:
                    both = int((self.df[col1] & self.df[col2]).sum())
                    if both > 0:
                        co_occurrences[f"{t1}+{t2}"] = both
        
        sorted_co = sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "multi_topic_count": multi_topic,
            "multi_topic_percentage": round(multi_topic / total * 100, 2) if total > 0 else 0,
            "no_topic_count": no_topic,
            "no_topic_percentage": round(no_topic / total * 100, 2) if total > 0 else 0,
            "topic_count_mean": round(float(topic_counts.mean()), 2),
            "top_co_occurrences": dict(sorted_co)
        }
    
    # visualizations

    def generate_visualizations(self, topic_stats: Dict, severity_stats: Dict) -> List[Path]:
        saved_paths = []
        reports_dir = self.get_reports_dir()
        
        plt.figure(figsize=(12, 6))
        topics = list(topic_stats.keys())
        percentages = [topic_stats[t]["percentage"] for t in topics]
        
        bars = plt.barh(topics, percentages, color='steelblue')
        plt.axvline(x=self.UNDERREPRESENTATION_THRESHOLD, color='red', 
                   linestyle='--', label=f'Threshold ({self.UNDERREPRESENTATION_THRESHOLD}%)')
        plt.xlabel('Percentage of Conversations')
        plt.title('Topic Distribution in Conversations')
        plt.legend()
        plt.tight_layout()
        
        topic_path = reports_dir / "topic_distribution.png"
        plt.savefig(topic_path, dpi=150)
        plt.close()
        saved_paths.append(topic_path)
        
        plt.figure(figsize=(8, 8))
        severities = list(severity_stats.keys())
        counts = [severity_stats[s]["count"] for s in severities]
        
        colors = {
            "crisis": "#d62728",
            "severe": "#ff7f0e", 
            "moderate": "#ffbb78",
            "mild": "#98df8a",
            "unknown": "#c7c7c7"
        }
        pie_colors = [colors.get(s, "#c7c7c7") for s in severities]
        
        plt.pie(counts, labels=severities, autopct='%1.1f%%', colors=pie_colors)
        plt.title('Severity Distribution')
        plt.tight_layout()
        
        severity_path = reports_dir / "severity_distribution.png"
        plt.savefig(severity_path, dpi=150)
        plt.close()
        saved_paths.append(severity_path)
        
        plt.figure(figsize=(12, 6))
        response_means = [topic_stats[t]["response_length_mean"] for t in topics]
        
        plt.bar(topics, response_means, color='teal')
        plt.xticks(rotation=45, ha='right')
        plt.ylabel('Average Response Word Count')
        plt.title('Response Length by Topic')
        plt.tight_layout()
        
        response_path = reports_dir / "response_length_by_topic.png"
        plt.savefig(response_path, dpi=150)
        plt.close()
        saved_paths.append(response_path)
        
        logger.info(f"Generated {len(saved_paths)} visualizations")
        return saved_paths
    
    # mitigation notes with bias type labels

    def generate_mitigation_notes(self, underrepresented: List[str], 
                                  cross_analysis: Dict,
                                  topic_overlap: Dict) -> List[str]:
        notes = []
        
        if underrepresented:
            notes.append(
                f"REPRESENTATION BIAS: Underrepresented topics ({', '.join(underrepresented)}): "
                f"Consider collecting more data for these topics to improve RAG coverage. "
                f"Certain clinical concerns have fewer examples in the dataset."
            )
        
        if cross_analysis.get("shorter_response_topics"):
            topics = [t["topic"] for t in cross_analysis["shorter_response_topics"]]
            notes.append(
                f"MEASUREMENT BIAS: Topics with shorter responses ({', '.join(topics)}): "
                f"May indicate lower counselor engagement on these topics. "
                f"Review if response quality is adequate for RAG retrieval."
            )
        
        if cross_analysis.get("longer_response_topics"):
            topics = [t["topic"] for t in cross_analysis["longer_response_topics"]]
            notes.append(
                f"MEASUREMENT BIAS: Topics with longer responses ({', '.join(topics)}): "
                f"Verbosity may affect RAG retrieval quality. "
                f"Consider chunking long responses for better embedding coverage."
            )
        
        no_topic_pct = topic_overlap.get("no_topic_percentage", 0)
        if no_topic_pct > 30:
            notes.append(
                f"COVERAGE GAP: {no_topic_pct}% of conversations match no defined topic. "
                f"Consider expanding topic keywords or adding new topic categories."
            )
        
        multi_pct = topic_overlap.get("multi_topic_percentage", 0)
        if multi_pct > 0:
            top_pairs = topic_overlap.get("top_co_occurrences", {})
            pair_str = ", ".join(f"{k} ({v})" for k, v in list(top_pairs.items())[:3])
            notes.append(
                f"Topic co-occurrence: {multi_pct}% of conversations match multiple topics. "
                f"Top pairs: {pair_str}. Multi-topic conversations may need specialized handling."
            )
        
        if not notes:
            notes.append(
                "No significant bias detected. Topic distribution, response quality, "
                "and severity distribution appear balanced."
            )
        
        return notes
    
    def generate_report(self, topic_stats: Dict, severity_stats: Dict,
                       underrepresented: List[str], cross_analysis: Dict,
                       topic_overlap: Dict,
                       mitigation_notes: List[str]) -> BiasReport:
        return BiasReport(
            dataset_name="conversations",
            timestamp=datetime.now().isoformat(),
            total_records=len(self.df),
            topic_distribution=topic_stats,
            severity_distribution=severity_stats,
            underrepresented_topics=underrepresented,
            cross_analysis=cross_analysis,
            topic_overlap=topic_overlap,
            mitigation_notes=mitigation_notes
        )
    
    def save_report(self, report: BiasReport) -> Path:
        output_path = self.get_reports_dir() / "conversation_bias_report.json"
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        logger.info(f"Saved bias report to {output_path}")
        return output_path
    
    def run(self, skip_existing: bool = True) -> Optional[BiasReport]:
        self.settings.ensure_directories()
        
        report_path = self.get_reports_dir() / "conversation_bias_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None
        
        self.load_data()
        self.classify_topics()
        self.classify_severity()
        
        topic_stats = self.analyze_topic_distribution()
        severity_stats = self.analyze_severity_distribution()
        underrepresented = self.find_underrepresented_topics(topic_stats)
        cross_analysis = self.cross_analyze(topic_stats)
        topic_overlap = self.analyze_topic_overlap()
        mitigation_notes = self.generate_mitigation_notes(underrepresented, cross_analysis, topic_overlap)
        
        self.generate_visualizations(topic_stats, severity_stats)
        
        report = self.generate_report(
            topic_stats, severity_stats, underrepresented, 
            cross_analysis, topic_overlap, mitigation_notes
        )
        self.save_report(report)
        
        logger.info(f"Bias analysis complete. Found {len(underrepresented)} underrepresented topics")
        return report


if __name__ == "__main__":
    analyzer = ConversationBiasAnalyzer()
    analyzer.run(skip_existing=False)
