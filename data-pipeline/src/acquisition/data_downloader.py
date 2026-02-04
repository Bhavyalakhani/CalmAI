"""
Download mental health counseling conversations from HuggingFace.
Handles multiple datasets with different column requirements.
"""
import logging
from pathlib import Path
from datasets import load_dataset
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MentalHealthDataDownloader:
    """Downloads and validates mental health conversation datasets."""
    
    # Dataset 1: Full download
    DATASET_1 = {
        "name": "Amod/mental_health_counseling_conversations",
        "output_file": "mental_health_conversations.parquet",
        "columns": None,  # Download all columns
        "expected_row_count": 3512
    }
    
    # Dataset 2: Partial download
    DATASET_2 = {
        "name": "nbertagnolli/counsel-chat",
        "output_file": "counsel_chat.parquet",
        "columns": ["questionTitle", "questionText", "answerText"],
        "expected_row_count": None  # Unknown, will just log
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def download_dataset(self, dataset_name: str, columns: list = None) -> pd.DataFrame:
        """Download dataset from HuggingFace."""
        logger.info(f"Downloading dataset: {dataset_name}")
        
        try:
            dataset = load_dataset(dataset_name, split="train")
            df = dataset.to_pandas()
            
            # Filter columns if specified
            if columns:
                missing_cols = set(columns) - set(df.columns)
                if missing_cols:
                    raise ValueError(f"Missing required columns: {missing_cols}")
                df = df[columns]
            
            logger.info(f"Downloaded {len(df)} records with {len(df.columns)} columns")
            return df
            
        except Exception as e:
            logger.error(f"Failed to download {dataset_name}: {e}")
            raise
    
    def validate_dataset(self, df: pd.DataFrame, dataset_info: dict) -> bool:
        """Validate dataset integrity."""
        errors = []
        warnings = []
        
        # Check row count if expected count is provided
        if dataset_info["expected_row_count"]:
            if len(df) != dataset_info["expected_row_count"]:
                warnings.append(
                    f"Row count mismatch: expected {dataset_info['expected_row_count']}, "
                    f"got {len(df)}"
                )
        
        # Check for nulls
        null_counts = df.isnull().sum()
        if null_counts.any():
            null_info = null_counts[null_counts > 0].to_dict()
            warnings.append(f"Null values found: {null_info}")
        
        # Check for empty strings in string columns
        for col in df.select_dtypes(include=['object']).columns:
            empty_count = (df[col].astype(str).str.strip() == "").sum()
            if empty_count > 0:
                warnings.append(f"Empty strings in {col}: {empty_count}")
        
        # Log warnings
        for warning in warnings:
            logger.warning(warning)
        
        # Log errors (if any critical issues)
        for error in errors:
            logger.error(error)
        
        if errors:
            return False
        
        logger.info("Validation completed")
        return True
    
    def save_dataset(self, df: pd.DataFrame, filename: str) -> Path:
        """Save dataset to parquet format."""
        output_path = self.output_dir / filename
        df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(df)} records to {output_path}")
        return output_path
    
    def download_and_save(self, dataset_info: dict) -> Path:
        """Download, validate, and save a single dataset."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {dataset_info['name']}")
        logger.info(f"{'='*60}")
        
        # Download
        df = self.download_dataset(
            dataset_info["name"], 
            dataset_info["columns"]
        )
        
        # Validate
        if not self.validate_dataset(df, dataset_info):
            raise ValueError(f"Validation failed for {dataset_info['name']}")
        
        # Save
        output_path = self.save_dataset(df, dataset_info["output_file"])
        
        return output_path
    
    def run(self) -> dict:
        """Execute full download pipeline for all datasets."""
        results = {}
        
        try:
            # Download dataset 1 (full)
            results["dataset_1"] = self.download_and_save(self.DATASET_1)
            
            # Download dataset 2 (partial)
            results["dataset_2"] = self.download_and_save(self.DATASET_2)
            
            logger.info(f"\n{'='*60}")
            logger.info("All datasets downloaded successfully!")
            logger.info(f"{'='*60}")
            for key, path in results.items():
                logger.info(f"{key}: {path}")
            
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise


if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent 
    output_dir = project_root / "data" / "raw" / "conversations"

    downloader = MentalHealthDataDownloader(output_dir=output_dir)
    output_paths = downloader.run()
    
    print("\n" + "="*60)
    print("DOWNLOAD COMPLETE")
    print("="*60)
    for dataset, path in output_paths.items():
        print(f"{dataset}: {path}")