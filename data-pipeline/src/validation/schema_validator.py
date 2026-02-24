# custom expectation-based schema validation
# checks column existence, uniqueness, nulls, ranges, types, and empty strings
# generates json reports with pass rates

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
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# result of a single expectation check
@dataclass
class ExpectationResult:
    name: str
    success: bool
    details: Dict[str, Any]


# full report with pass/fail stats
@dataclass
class ValidationReport:
    dataset_name: str
    timestamp: str
    total_records: int
    passed: int
    failed: int
    pass_rate: float
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
    
    # expectation primitives

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
        success = bool(duplicates == 0)
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
        success = bool(null_count == 0)
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
        
        success = bool(violations == 0)
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
    
    def expect_column_type(self, df: pd.DataFrame, column: str, expected_type: str) -> ExpectationResult:
        if column not in df.columns:
            return ExpectationResult(
                name=f"column_type_{column}",
                success=False,
                details={"column": column, "error": "column not found"}
            )
        
        actual_type = str(df[column].dtype)
        success = expected_type.lower() in actual_type.lower()
        return ExpectationResult(
            name=f"column_type_{column}",
            success=success,
            details={
                "column": column,
                "expected_type": expected_type,
                "actual_type": actual_type
            }
        )
    
    def expect_string_not_empty(self, df: pd.DataFrame, column: str) -> ExpectationResult:
        if column not in df.columns:
            return ExpectationResult(
                name=f"string_not_empty_{column}",
                success=False,
                details={"column": column, "error": "column not found"}
            )
        
        empty_count = (df[column].astype(str).str.strip() == "").sum()
        success = bool(empty_count == 0)
        return ExpectationResult(
            name=f"string_not_empty_{column}",
            success=success,
            details={"column": column, "empty_count": int(empty_count)}
        )
    
    # text statistics helpers

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
    
    # full dataset validators

    def validate_conversations(self, df: pd.DataFrame) -> List[ExpectationResult]:
        logger.info(f"Running conversation schema validation on {len(df)} records")
        results = []

        # column existence
        required_columns = ["conversation_id", "context", "response", "embedding_text"]
        for col in required_columns:
            results.append(self.expect_column_exists(df, col))
        
        # uniqueness
        results.append(self.expect_column_unique(df, "conversation_id"))

        # nulls
        results.append(self.expect_column_not_null(df, "conversation_id"))
        results.append(self.expect_column_not_null(df, "context"))
        results.append(self.expect_column_not_null(df, "response"))
        results.append(self.expect_column_not_null(df, "embedding_text"))
        
        # empty string checks
        results.append(self.expect_string_not_empty(df, "context"))
        results.append(self.expect_string_not_empty(df, "response"))
        results.append(self.expect_string_not_empty(df, "embedding_text"))
        
        # numeric range checks
        if "context_word_count" in df.columns:
            results.append(self.expect_value_range(df, "context_word_count", min_val=3, max_val=5000))
        
        if "response_word_count" in df.columns:
            results.append(self.expect_value_range(df, "response_word_count", min_val=3, max_val=10000))
        
        if "context_char_count" in df.columns:
            results.append(self.expect_value_range(df, "context_char_count", min_val=10, max_val=50000))
        
        if "response_char_count" in df.columns:
            results.append(self.expect_value_range(df, "response_char_count", min_val=10, max_val=100000))
        
        if "context_sentence_count" in df.columns:
            results.append(self.expect_value_range(df, "context_sentence_count", min_val=1, max_val=500))
        
        if "response_sentence_count" in df.columns:
            results.append(self.expect_value_range(df, "response_sentence_count", min_val=1, max_val=1000))
        
        if "context_avg_word_length" in df.columns:
            results.append(self.expect_value_range(df, "context_avg_word_length", min_val=1.0, max_val=30.0))
        
        if "response_avg_word_length" in df.columns:
            results.append(self.expect_value_range(df, "response_avg_word_length", min_val=1.0, max_val=30.0))
        
        passed = sum(1 for r in results if r.success)
        logger.info(f"Conversation validation complete: {passed}/{len(results)} checks passed")
        return results
    
    def validate_journals(self, df: pd.DataFrame) -> List[ExpectationResult]:
        logger.info(f"Running journal schema validation on {len(df)} records")
        results = []

        # column existence
        required_columns = ["journal_id", "patient_id", "therapist_id", "entry_date", "content"]
        for col in required_columns:
            results.append(self.expect_column_exists(df, col))
        
        # uniqueness
        results.append(self.expect_column_unique(df, "journal_id"))

        # nulls
        results.append(self.expect_column_not_null(df, "journal_id"))
        results.append(self.expect_column_not_null(df, "patient_id"))
        results.append(self.expect_column_not_null(df, "therapist_id"))
        results.append(self.expect_column_not_null(df, "entry_date"))
        results.append(self.expect_column_not_null(df, "content"))
        
        # empty string checks
        results.append(self.expect_string_not_empty(df, "content"))

        # type checks
        results.append(self.expect_column_type(df, "entry_date", "datetime"))

        # embedding text checks
        if "embedding_text" in df.columns:
            results.append(self.expect_column_not_null(df, "embedding_text"))
            results.append(self.expect_string_not_empty(df, "embedding_text"))
        
        # text stat ranges
        if "word_count" in df.columns:
            results.append(self.expect_value_range(df, "word_count", min_val=3, max_val=1000))
        
        if "char_count" in df.columns:
            results.append(self.expect_value_range(df, "char_count", min_val=10, max_val=10000))
        
        if "sentence_count" in df.columns:
            results.append(self.expect_value_range(df, "sentence_count", min_val=1, max_val=200))
        
        if "avg_word_length" in df.columns:
            results.append(self.expect_value_range(df, "avg_word_length", min_val=1.0, max_val=30.0))
        
        # temporal ranges
        if "day_of_week" in df.columns:
            results.append(self.expect_value_range(df, "day_of_week", min_val=0, max_val=6))
        
        if "week_number" in df.columns:
            results.append(self.expect_value_range(df, "week_number", min_val=1, max_val=53))
        
        if "month" in df.columns:
            results.append(self.expect_value_range(df, "month", min_val=1, max_val=12))
        
        if "year" in df.columns:
            results.append(self.expect_value_range(df, "year", min_val=2020, max_val=2030))
        
        if "days_since_last" in df.columns:
            results.append(self.expect_value_range(df, "days_since_last", min_val=0, max_val=365))
        
        passed = sum(1 for r in results if r.success)
        logger.info(f"Journal validation complete: {passed}/{len(results)} checks passed")
        return results
    
    # report generation and saving

    def generate_report(self, dataset_name: str, df: pd.DataFrame, 
                       results: List[ExpectationResult], 
                       text_columns: List[str]) -> ValidationReport:
        
        statistics = {"record_count": len(df)}
        
        for col in text_columns:
            statistics.update(self.compute_text_statistics(df, col))
            statistics.update(self.compute_vocabulary_stats(df, col))
        
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        pass_rate = round((passed / len(results)) * 100, 2) if results else 0.0
        
        return ValidationReport(
            dataset_name=dataset_name,
            timestamp=datetime.now().isoformat(),
            total_records=len(df),
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
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
        
        logger.info("Step 1/3: Loading processed conversations")
        df = pd.read_parquet(data_path)
        logger.info(f"  Loaded {len(df)} conversations")
        
        logger.info("Step 2/3: Running validation expectations")
        results = self.validate_conversations(df)
        report = self.generate_report(
            "conversations", 
            df, 
            results, 
            ["context", "response"]
        )
        
        logger.info("Step 3/3: Saving validation report")
        self.save_report(report, "conversations_schema_report.json")
        
        logger.info(f"Conversations validation: {report.passed}/{report.passed + report.failed} passed ({report.pass_rate}%)")
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
        
        logger.info("Step 1/3: Loading processed journals")
        df = pd.read_parquet(data_path)
        logger.info(f"  Loaded {len(df)} journals")
        
        logger.info("Step 2/3: Running validation expectations")
        results = self.validate_journals(df)
        report = self.generate_report(
            "journals",
            df,
            results,
            ["content"]
        )
        
        logger.info("Step 3/3: Saving validation report")
        self.save_report(report, "journals_schema_report.json")
        
        logger.info(f"Journals validation: {report.passed}/{report.passed + report.failed} passed ({report.pass_rate}%)")
        return report
    
    def run(self, skip_existing: bool = True) -> Dict[str, Optional[ValidationReport]]:
        self.settings.ensure_directories()
        
        return {
            "conversations": self.run_conversations(skip_existing),
            "journals": self.run_journals(skip_existing)
        }

    # incoming journal validation for dag 2 (runtime entries from backend)

    def validate_incoming_journals(self, df: pd.DataFrame) -> List[ExpectationResult]:
        """validate incoming journals before embedding and storage.
        checks content length, required fields, date validity, and spam patterns."""
        import re
        logger.info(f"Validating {len(df)} incoming journal entries")
        results = []

        # required columns
        for col in ["journal_id", "patient_id", "content"]:
            results.append(self.expect_column_exists(df, col))
            results.append(self.expect_column_not_null(df, col))

        # content must not be empty
        if "content" in df.columns:
            results.append(self.expect_string_not_empty(df, "content"))

        # content length bounds
        min_len = self.settings.INCOMING_JOURNAL_MIN_LENGTH
        max_len = self.settings.INCOMING_JOURNAL_MAX_LENGTH

        if "content" in df.columns:
            lengths = df["content"].astype(str).str.len()
            too_short = int((lengths < min_len).sum())
            too_long = int((lengths > max_len).sum())
            results.append(ExpectationResult(
                name="content_length_bounds",
                success=bool(too_short == 0 and too_long == 0),
                details={
                    "min_length": min_len,
                    "max_length": max_len,
                    "too_short": too_short,
                    "too_long": too_long,
                }
            ))

            # detect spam / low-quality content (repeated chars, all caps, url-only)
            def _is_spam(text: str) -> bool:
                if len(text) > 20 and len(set(text.strip())) <= 2:
                    return True
                if len(text) > 50 and text.strip() == text.strip().upper() and text.strip().isalpha():
                    return True
                if text.strip().startswith("http://") or text.strip().startswith("https://"):
                    return True
                return False

            spam_count = int(df["content"].astype(str).apply(_is_spam).sum())
            results.append(ExpectationResult(
                name="content_not_spam",
                success=bool(spam_count == 0),
                details={"spam_count": spam_count}
            ))

        # entry_date should not be in the future
        if "entry_date" in df.columns:
            dates = pd.to_datetime(df["entry_date"], errors="coerce", utc=True)
            future_count = int((dates > pd.Timestamp.now(tz="UTC")).sum())
            results.append(ExpectationResult(
                name="entry_date_not_future",
                success=bool(future_count == 0),
                details={"future_count": future_count}
            ))

        # journal_id uniqueness within batch
        if "journal_id" in df.columns:
            results.append(self.expect_column_unique(df, "journal_id"))

        passed = sum(1 for r in results if r.success)
        logger.info(f"Incoming journal validation: {passed}/{len(results)} checks passed")
        return results


if __name__ == "__main__":
    validator = SchemaValidator()
    validator.run(skip_existing=False)
