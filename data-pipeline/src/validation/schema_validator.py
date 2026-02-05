import json
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "configs"))
import config # pyright: ignore[reportMissingImports]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ExpectationResult:
    name: str
    success: bool
    details: Dict[str, Any]


@dataclass
class ValidationReport:
    dataset_name: str
    timestamp: str
    total_records: int
    passed: int
    failed: int
    expectations: List[Dict]
    statistics: Dict[str, Any]


class SchemaValidator:
    
    def __init__(self):
        self.settings = config.settings
        self.results = []
    
    def get_conversations_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "conversations" / "processed_conversations.parquet"
    
    def get_journals_path(self) -> Path:
        return self.settings.PROCESSED_DATA_DIR / "journals" / "processed_journals.parquet"
    
    def get_reports_dir(self) -> Path:
        reports_dir = self.settings.REPORTS_DIR / "schema"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir
    
    def expect_column_exists(self, df: pd.DataFrame, column: str) -> ExpectationResult:
        success = column in df.columns
        return ExpectationResult(
            name=f"column_exists_{column}",
            success=success,
            details={"column": column, "found": success}
        )
    
    def expect_column_unique(self, df: pd.DataFrame, column: str) -> ExpectationResult:
        if column not in df.columns:
            return ExpectationResult(
                name=f"column_unique_{column}",
                success=False,
                details={"column": column, "error": "column not found"}
            )
        
        duplicates = df[column].duplicated().sum()
        success = duplicates == 0
        return ExpectationResult(
            name=f"column_unique_{column}",
            success=success,
            details={"column": column, "duplicates": int(duplicates)}
        )
    
    def expect_column_not_null(self, df: pd.DataFrame, column: str) -> ExpectationResult:
        if column not in df.columns:
            return ExpectationResult(
                name=f"column_not_null_{column}",
                success=False,
                details={"column": column, "error": "column not found"}
            )
        
        null_count = df[column].isna().sum()
        success = null_count == 0
        return ExpectationResult(
            name=f"column_not_null_{column}",
            success=success,
            details={"column": column, "null_count": int(null_count)}
        )
    
    def expect_value_range(self, df: pd.DataFrame, column: str, 
                          min_val: Optional[float] = None, 
                          max_val: Optional[float] = None) -> ExpectationResult:
        if column not in df.columns:
            return ExpectationResult(
                name=f"value_range_{column}",
                success=False,
                details={"column": column, "error": "column not found"}
            )
        
        violations = 0
        if min_val is not None:
            violations += (df[column] < min_val).sum()
        if max_val is not None:
            violations += (df[column] > max_val).sum()
        
        success = violations == 0
        return ExpectationResult(
            name=f"value_range_{column}",
            success=success,
            details={
                "column": column,
                "min_expected": min_val,
                "max_expected": max_val,
                "actual_min": float(df[column].min()) if len(df) > 0 else None,
                "actual_max": float(df[column].max()) if len(df) > 0 else None,
                "violations": int(violations)
            }
        )
    
    def compute_text_statistics(self, df: pd.DataFrame, text_column: str) -> Dict[str, Any]:
        if text_column not in df.columns:
            return {}
        
        text_lengths = df[text_column].str.len()
        word_counts = df[text_column].str.split().str.len()
        
        return {
            f"{text_column}_length_min": int(text_lengths.min()),
            f"{text_column}_length_max": int(text_lengths.max()),
            f"{text_column}_length_mean": round(float(text_lengths.mean()), 2),
            f"{text_column}_length_std": round(float(text_lengths.std()), 2),
            f"{text_column}_words_min": int(word_counts.min()),
            f"{text_column}_words_max": int(word_counts.max()),
            f"{text_column}_words_mean": round(float(word_counts.mean()), 2),
        }
    
    def compute_vocabulary_stats(self, df: pd.DataFrame, text_column: str) -> Dict[str, Any]:
        if text_column not in df.columns:
            return {}
        
        all_text = " ".join(df[text_column].dropna().astype(str))
        words = all_text.lower().split()
        unique_words = set(words)
        
        return {
            f"{text_column}_total_words": len(words),
            f"{text_column}_unique_words": len(unique_words),
            f"{text_column}_vocab_richness": round(len(unique_words) / len(words), 4) if words else 0
        }
    
    def validate_conversations(self, df: pd.DataFrame) -> List[ExpectationResult]:
        results = []
        
        required_columns = ["conversation_id", "context", "response", "embedding_text"]
        for col in required_columns:
            results.append(self.expect_column_exists(df, col))
        
        results.append(self.expect_column_unique(df, "conversation_id"))
        results.append(self.expect_column_not_null(df, "conversation_id"))
        results.append(self.expect_column_not_null(df, "context"))
        results.append(self.expect_column_not_null(df, "response"))
        
        if "context_word_count" in df.columns:
            results.append(self.expect_value_range(df, "context_word_count", min_val=3, max_val=5000))
        
        if "response_word_count" in df.columns:
            results.append(self.expect_value_range(df, "response_word_count", min_val=3, max_val=10000))
        
        return results
    
    def validate_journals(self, df: pd.DataFrame) -> List[ExpectationResult]:
        results = []
        
        required_columns = ["journal_id", "patient_id", "therapist_id", "entry_date", "content"]
        for col in required_columns:
            results.append(self.expect_column_exists(df, col))
        
        results.append(self.expect_column_unique(df, "journal_id"))
        results.append(self.expect_column_not_null(df, "journal_id"))
        results.append(self.expect_column_not_null(df, "patient_id"))
        results.append(self.expect_column_not_null(df, "content"))
        
        if "word_count" in df.columns:
            results.append(self.expect_value_range(df, "word_count", min_val=3, max_val=1000))
        
        return results
    
    def generate_report(self, dataset_name: str, df: pd.DataFrame, 
                       results: List[ExpectationResult], 
                       text_columns: List[str]) -> ValidationReport:
        
        statistics = {"record_count": len(df)}
        
        for col in text_columns:
            statistics.update(self.compute_text_statistics(df, col))
            statistics.update(self.compute_vocabulary_stats(df, col))
        
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        
        return ValidationReport(
            dataset_name=dataset_name,
            timestamp=datetime.now().isoformat(),
            total_records=len(df),
            passed=passed,
            failed=failed,
            expectations=[asdict(r) for r in results],
            statistics=statistics
        )
    
    def save_report(self, report: ValidationReport, filename: str) -> Path:
        output_path = self.get_reports_dir() / filename
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)
        logger.info(f"Saved report to {output_path}")
        return output_path
    
    def run_conversations(self, skip_existing: bool = True) -> Optional[ValidationReport]:
        report_path = self.get_reports_dir() / "conversations_schema_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None
        
        data_path = self.get_conversations_path()
        if not data_path.exists():
            logger.warning(f"Conversations data not found: {data_path}")
            return None
        
        df = pd.read_parquet(data_path)
        logger.info(f"Validating {len(df)} conversations")
        
        results = self.validate_conversations(df)
        report = self.generate_report(
            "conversations", 
            df, 
            results, 
            ["context", "response"]
        )
        
        self.save_report(report, "conversations_schema_report.json")
        
        logger.info(f"Validation: {report.passed} passed, {report.failed} failed")
        return report
    
    def run_journals(self, skip_existing: bool = True) -> Optional[ValidationReport]:
        report_path = self.get_reports_dir() / "journals_schema_report.json"
        if skip_existing and report_path.exists():
            logger.info(f"Report already exists: {report_path}")
            return None
        
        data_path = self.get_journals_path()
        if not data_path.exists():
            logger.warning(f"Journals data not found: {data_path}")
            return None
        
        df = pd.read_parquet(data_path)
        logger.info(f"Validating {len(df)} journals")
        
        results = self.validate_journals(df)
        report = self.generate_report(
            "journals",
            df,
            results,
            ["content"]
        )
        
        self.save_report(report, "journals_schema_report.json")
        
        logger.info(f"Validation: {report.passed} passed, {report.failed} failed")
        return report
    
    def run(self, skip_existing: bool = True) -> Dict[str, Optional[ValidationReport]]:
        self.settings.ensure_directories()
        
        return {
            "conversations": self.run_conversations(skip_existing),
            "journals": self.run_journals(skip_existing)
        }


if __name__ == "__main__":
    validator = SchemaValidator()
    validator.run(skip_existing=False)
