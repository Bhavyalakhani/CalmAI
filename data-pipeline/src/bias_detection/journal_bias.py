# bias analysis for the journals dataset
# analyzes patient distribution, sparse patients, temporal patterns,
# theme classification (8 categories), theme overlap, and generates
# visualizations + mitigation notes with bias type labels

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

from .slicer import DataSlicer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class JournalBiasReport:
    dataset_name: str
    timestamp: str
    total_records: int
    total_patients: int
    patient_distribution: Dict[str, Any]
    temporal_patterns: Dict[str, Any]
    theme_distribution: Dict[str, Dict[str, Any]]
    theme_overlap: Dict[str, Any]
    sparse_patients: List[Dict[str, Any]]
    mitigation_notes: List[str]


class JournalBiasAnalyzer:
    
    # 8 journal themes with keyword lists
    THEMES = {
        "anxiety": ["anxious", "anxiety", "worry", "worried", "panic", "nervous"],
        "depression": ["depressed", "depression", "hopeless", "sad", "empty", "low"],
        "positive": ["happy", "good", "better", "progress", "grateful", "hopeful"],
        "negative": ["bad", "worse", "terrible", "awful", "horrible", "struggling"],
        "therapy": ["therapy", "therapist", "session", "counselor", "appointment"],
        "sleep": ["sleep", "insomnia", "tired", "exhausted", "rest", "nightmare"],
        "social": ["friend", "family", "people", "social", "lonely", "isolated"],
        "work": ["work", "job", "career", "boss", "stress", "deadline"]
    }
    
    # patients with fewer entries than this are flagged
    SPARSE_THRESHOLD = 10
    
    def __init__(self):
        self.settings = config.settings
        self.df = None
        self.slicer = None
    
    def get_input_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
    
    def get_reports_dir(self) -> Path:
        reports_dir = self.settings.REPORTS_DIR / "bias"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir
    
    def load_data(self) -> pd.DataFrame:
        input_path = self.get_input_path()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Processed journals not found: {input_path}")
        
        self.df = pd.read_parquet(input_path)
        self.slicer = DataSlicer(self.df)
        logger.info(f"Loaded {len(self.df)} journal entries for bias analysis")
        return self.df
    
    # patient distribution analysis

    def analyze_patient_distribution(self) -> Dict[str, Any]:
        patient_counts = self.df.groupby("patient_id").size()
        
        return {
            "total_patients": len(patient_counts),
            "entries_per_patient_mean": round(float(patient_counts.mean()), 2),
            "entries_per_patient_std": round(float(patient_counts.std()), 2),
            "entries_per_patient_min": int(patient_counts.min()),
            "entries_per_patient_max": int(patient_counts.max()),
            "entries_per_patient_median": float(patient_counts.median())
        }
    
    def find_sparse_patients(self) -> List[Dict[str, Any]]:
        patient_counts = self.df.groupby("patient_id").size()
        sparse = patient_counts[patient_counts < self.SPARSE_THRESHOLD]
        
        sparse_list = []
        for patient_id, count in sparse.items():
            sparse_list.append({
                "patient_id": str(patient_id),
                "entry_count": int(count)
            })
        
        return sparse_list
    
    # temporal patterns — entries by day/month, gap stats

    def analyze_temporal_patterns(self) -> Dict[str, Any]:
        patterns = {}
        
        if "day_of_week" in self.df.columns:
            day_counts = self.df["day_of_week"].value_counts().sort_index()
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            patterns["entries_by_day"] = {
                day_names[int(k)]: int(v) for k, v in day_counts.items() if pd.notna(k)
            }
        
        if "month" in self.df.columns:
            month_counts = self.df["month"].value_counts().sort_index()
            patterns["entries_by_month"] = {int(k): int(v) for k, v in month_counts.items() if pd.notna(k)}
        
        if "days_since_last" in self.df.columns:
            valid_gaps = self.df["days_since_last"][self.df["days_since_last"] > 0]
            if len(valid_gaps) > 0:
                patterns["entry_gap_mean"] = round(float(valid_gaps.mean()), 2)
                patterns["entry_gap_median"] = float(valid_gaps.median())
                patterns["entry_gap_max"] = int(valid_gaps.max())
        
        return patterns
    
    # theme classification and distribution

    def classify_themes(self) -> pd.DataFrame:
        for theme, keywords in self.THEMES.items():
            pattern = "|".join(keywords)
            self.df[f"theme_{theme}"] = self.df["content"].str.contains(
                pattern, case=False, na=False
            )
        return self.df
    
    def analyze_theme_distribution(self) -> Dict[str, Dict[str, Any]]:
        theme_stats = {}
        total = len(self.df)
        
        for theme in self.THEMES.keys():
            col = f"theme_{theme}"
            if col not in self.df.columns:
                continue
            
            theme_df = self.df[self.df[col]]
            count = len(theme_df)
            percentage = (count / total * 100) if total > 0 else 0
            
            word_count_mean = 0
            if "word_count" in theme_df.columns and count > 0:
                word_count_mean = float(theme_df["word_count"].mean())
            
            theme_stats[theme] = {
                "count": count,
                "percentage": round(percentage, 2),
                "word_count_mean": round(word_count_mean, 2)
            }
        
        return theme_stats
    
    # how many entries match >1 theme, and top co-occurring pairs
    def analyze_theme_overlap(self) -> Dict[str, Any]:
        theme_cols = [f"theme_{t}" for t in self.THEMES if f"theme_{t}" in self.df.columns]
        
        if not theme_cols:
            return {}
        
        theme_counts = self.df[theme_cols].sum(axis=1)
        
        multi_theme = int((theme_counts > 1).sum())
        no_theme = int((theme_counts == 0).sum())
        total = len(self.df)
        
        # Top co-occurring theme pairs
        co_occurrences = {}
        theme_names = list(self.THEMES.keys())
        for i, t1 in enumerate(theme_names):
            for t2 in theme_names[i + 1:]:
                col1, col2 = f"theme_{t1}", f"theme_{t2}"
                if col1 in self.df.columns and col2 in self.df.columns:
                    both = int((self.df[col1] & self.df[col2]).sum())
                    if both > 0:
                        co_occurrences[f"{t1}+{t2}"] = both
        
        sorted_co = sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "multi_theme_count": multi_theme,
            "multi_theme_percentage": round(multi_theme / total * 100, 2) if total > 0 else 0,
            "no_theme_count": no_theme,
            "no_theme_percentage": round(no_theme / total * 100, 2) if total > 0 else 0,
            "theme_count_mean": round(float(theme_counts.mean()), 2),
            "top_co_occurrences": dict(sorted_co)
        }
    
    # visualizations

    def generate_visualizations(self, patient_dist: Dict, temporal: Dict, 
                               theme_stats: Dict) -> List[Path]:
        saved_paths = []
        reports_dir = self.get_reports_dir()
        
        if "entries_by_day" in temporal:
            plt.figure(figsize=(10, 5))
            days = list(temporal["entries_by_day"].keys())
            counts = list(temporal["entries_by_day"].values())
            
            plt.bar(days, counts, color='steelblue')
            plt.xlabel('Day of Week')
            plt.ylabel('Number of Entries')
            plt.title('Journal Entries by Day of Week')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            day_path = reports_dir / "journal_entries_by_day.png"
            plt.savefig(day_path, dpi=150)
            plt.close()
            saved_paths.append(day_path)
        
        plt.figure(figsize=(12, 6))
        themes = list(theme_stats.keys())
        percentages = [theme_stats[t]["percentage"] for t in themes]
        
        colors = []
        for theme in themes:
            if theme == "positive":
                colors.append("#2ecc71")
            elif theme in ["anxiety", "depression", "negative"]:
                colors.append("#e74c3c")
            else:
                colors.append("#3498db")
        
        plt.barh(themes, percentages, color=colors)
        plt.xlabel('Percentage of Entries')
        plt.title('Theme Distribution in Journal Entries')
        plt.tight_layout()
        
        theme_path = reports_dir / "journal_theme_distribution.png"
        plt.savefig(theme_path, dpi=150)
        plt.close()
        saved_paths.append(theme_path)
        
        if "entries_by_month" in temporal:
            plt.figure(figsize=(10, 5))
            months = list(temporal["entries_by_month"].keys())
            counts = list(temporal["entries_by_month"].values())
            
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_labels = [month_names[m-1] if 1 <= m <= 12 else str(m) for m in months]
            
            plt.bar(month_labels, counts, color='teal')
            plt.xlabel('Month')
            plt.ylabel('Number of Entries')
            plt.title('Journal Entries by Month')
            plt.tight_layout()
            
            month_path = reports_dir / "journal_entries_by_month.png"
            plt.savefig(month_path, dpi=150)
            plt.close()
            saved_paths.append(month_path)
        
        logger.info(f"Generated {len(saved_paths)} visualizations")
        return saved_paths
    
    # mitigation notes with bias type labels

    def generate_mitigation_notes(self, sparse_patients: List, 
                                  temporal: Dict, theme_stats: Dict,
                                  patient_dist: Dict,
                                  theme_overlap: Dict) -> List[str]:
        notes = []
        
        # Patient representation analysis
        if patient_dist:
            std = patient_dist.get("entries_per_patient_std", 0)
            if std > 20:
                notes.append(
                    f"REPRESENTATION BIAS: High variance in entries per patient (std={std}). "
                    f"Some patients are over/under-represented. "
                    f"Consider re-sampling or weighting to balance patient representation."
                )
        
        if sparse_patients:
            patient_ids = [p["patient_id"] for p in sparse_patients[:5]]
            notes.append(
                f"REPRESENTATION BIAS: {len(sparse_patients)} patients with fewer than "
                f"{self.SPARSE_THRESHOLD} entries ({', '.join(patient_ids)}). "
                f"These patients may be underrepresented in downstream analysis. "
                f"Consider collecting more entries or applying upsampling."
            )
        
        # Temporal analysis
        if "entry_gap_max" in temporal and temporal["entry_gap_max"] > 30:
            notes.append(
                f"TEMPORAL BIAS: Maximum gap of {temporal['entry_gap_max']} days between entries. "
                f"Large gaps may indicate disengagement or crisis periods that skew temporal analysis."
            )
        
        if "entry_gap_mean" in temporal:
            notes.append(
                f"Temporal pattern: Average entry gap is {temporal['entry_gap_mean']} days "
                f"(median: {temporal.get('entry_gap_median', 'N/A')}). "
                f"Consistent journaling frequency supports reliable temporal analysis."
            )
        
        # Theme balance analysis
        theme_percentages = {t: s.get("percentage", 0) for t, s in theme_stats.items()}
        if theme_percentages:
            max_theme = max(theme_percentages, key=theme_percentages.get)
            min_theme = min(theme_percentages, key=theme_percentages.get)
            max_pct = theme_percentages[max_theme]
            min_pct = theme_percentages[min_theme]
            
            if min_pct > 0 and max_pct > 3 * min_pct:
                notes.append(
                    f"REPRESENTATION BIAS: Theme imbalance — '{max_theme}' ({max_pct}%) "
                    f"is {round(max_pct / min_pct, 1)}x more frequent than '{min_theme}' ({min_pct}%). "
                    f"Consider augmenting underrepresented themes for balanced RAG retrieval."
                )
        
        positive_pct = theme_stats.get("positive", {}).get("percentage", 0)
        negative_pct = theme_stats.get("negative", {}).get("percentage", 0)
        
        if positive_pct < 10:
            notes.append(
                "MEASUREMENT BIAS: Low positive-themed entries. Dataset skews toward "
                "problem-focused content, which could bias sentiment analysis."
            )
        
        if negative_pct > 50:
            notes.append(
                "MEASUREMENT BIAS: High negative-themed entries. Consider balancing with "
                "recovery-focused or neutral entries for RAG diversity."
            )
        
        # Theme overlap analysis
        if theme_overlap:
            no_theme_pct = theme_overlap.get("no_theme_percentage", 0)
            if no_theme_pct > 30:
                notes.append(
                    f"COVERAGE GAP: {no_theme_pct}% of entries match no defined theme. "
                    f"Consider expanding theme keywords or adding new theme categories."
                )
            multi_pct = theme_overlap.get("multi_theme_percentage", 0)
            if multi_pct > 0:
                top_pairs = theme_overlap.get("top_co_occurrences", {})
                pair_str = ", ".join(f"{k} ({v})" for k, v in list(top_pairs.items())[:3])
                notes.append(
                    f"Theme co-occurrence: {multi_pct}% of entries match multiple themes. "
                    f"Top pairs: {pair_str}. Multi-theme entries indicate complex patient states."
                )
        
        if not notes:
            notes.append(
                "No significant bias detected. Patient distribution, theme balance, "
                "and temporal patterns appear balanced across the dataset."
            )
        
        return notes
    
    def generate_report(self, patient_dist: Dict, temporal: Dict, 
                       theme_stats: Dict, theme_overlap: Dict,
                       sparse_patients: List,
                       mitigation_notes: List) -> JournalBiasReport:
        return JournalBiasReport(
            dataset_name="journals",
            timestamp=datetime.now().isoformat(),
            total_records=len(self.df),
            total_patients=self.df["patient_id"].nunique() if "patient_id" in self.df.columns else 0,
            patient_distribution=patient_dist,
            temporal_patterns=temporal,
            theme_distribution=theme_stats,
            theme_overlap=theme_overlap,
            sparse_patients=sparse_patients,
            mitigation_notes=mitigation_notes
        )
    
    def save_report(self, report: JournalBiasReport) -> Path:
        output_path = self.get_reports_dir() / "journal_bias_report.json"
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        logger.info(f"Saved bias report to {output_path}")
        return output_path
    
    def run(self, skip_existing: bool = True) -> Optional[JournalBiasReport]:
        self.settings.ensure_directories()
        
        report_path = self.get_reports_dir() / "journal_bias_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None
        
        self.load_data()
        self.classify_themes()
        
        patient_dist = self.analyze_patient_distribution()
        temporal = self.analyze_temporal_patterns()
        theme_stats = self.analyze_theme_distribution()
        theme_overlap = self.analyze_theme_overlap()
        sparse_patients = self.find_sparse_patients()
        mitigation_notes = self.generate_mitigation_notes(
            sparse_patients, temporal, theme_stats, patient_dist, theme_overlap
        )
        
        self.generate_visualizations(patient_dist, temporal, theme_stats)
        
        report = self.generate_report(
            patient_dist, temporal, theme_stats, theme_overlap,
            sparse_patients, mitigation_notes
        )
        self.save_report(report)
        
        logger.info(f"Bias analysis complete. Found {len(sparse_patients)} sparse patients")
        return report


if __name__ == "__main__":
    analyzer = JournalBiasAnalyzer()
    analyzer.run(skip_existing=False)
