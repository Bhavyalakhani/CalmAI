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
import config # pyright: ignore[reportMissingImports]

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
    mitigation_notes: List[str]


class ConversationBiasAnalyzer:
    
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
    
    SEVERITY = {
        "crisis": ["suicide", "kill myself", "emergency", "crisis", "can't go on", "end it all"],
        "severe": ["can't cope", "unbearable", "desperate", "breaking down", "falling apart"],
        "moderate": ["struggling", "difficult", "hard time", "overwhelmed", "stressed"],
        "mild": ["sometimes", "occasionally", "minor", "a little", "slightly"]
    }
    
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
    
    def classify_topics(self) -> pd.DataFrame:
        for topic, keywords in self.TOPICS.items():
            pattern = "|".join(keywords)
            self.df[f"topic_{topic}"] = self.df["context"].str.contains(
                pattern, case=False, na=False
            )
        return self.df
    
    def classify_severity(self) -> pd.DataFrame:
        self.df["severity"] = "unknown"
        
        for severity, keywords in self.SEVERITY.items():
            pattern = "|".join(keywords)
            mask = self.df["context"].str.contains(pattern, case=False, na=False)
            self.df.loc[mask, "severity"] = severity
        
        return self.df
    
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
        severity_stats = {}
        total = len(self.df)
        
        for severity in list(self.SEVERITY.keys()) + ["unknown"]:
            severity_df = self.df[self.df["severity"] == severity]
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
    
    def generate_mitigation_notes(self, underrepresented: List[str], 
                                  cross_analysis: Dict) -> List[str]:
        notes = []
        
        if underrepresented:
            notes.append(
                f"Underrepresented topics ({', '.join(underrepresented)}): "
                f"Consider collecting more data for these topics to improve RAG coverage"
            )
        
        if cross_analysis.get("shorter_response_topics"):
            topics = [t["topic"] for t in cross_analysis["shorter_response_topics"]]
            notes.append(
                f"Topics with shorter responses ({', '.join(topics)}): "
                f"May need quality review or additional counselor training data"
            )
        
        if cross_analysis.get("longer_response_topics"):
            topics = [t["topic"] for t in cross_analysis["longer_response_topics"]]
            notes.append(
                f"Topics with longer responses ({', '.join(topics)}): "
                f"Consider if verbosity affects RAG retrieval quality"
            )
        
        return notes
    
    def generate_report(self, topic_stats: Dict, severity_stats: Dict,
                       underrepresented: List[str], cross_analysis: Dict,
                       mitigation_notes: List[str]) -> BiasReport:
        return BiasReport(
            dataset_name="conversations",
            timestamp=datetime.now().isoformat(),
            total_records=len(self.df),
            topic_distribution=topic_stats,
            severity_distribution=severity_stats,
            underrepresented_topics=underrepresented,
            cross_analysis=cross_analysis,
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
        mitigation_notes = self.generate_mitigation_notes(underrepresented, cross_analysis)
        
        self.generate_visualizations(topic_stats, severity_stats)
        
        report = self.generate_report(
            topic_stats, severity_stats, underrepresented, 
            cross_analysis, mitigation_notes
        )
        self.save_report(report)
        
        logger.info(f"Bias analysis complete. Found {len(underrepresented)} underrepresented topics")
        return report


if __name__ == "__main__":
    analyzer = ConversationBiasAnalyzer()
    analyzer.run(skip_existing=False)
