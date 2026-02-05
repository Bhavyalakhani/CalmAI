import logging
from pathlib import Path
from datasets import load_dataset
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataDownloader:
    
    DATASET_1 = {
        "name": "Amod/mental_health_counseling_conversations",
        "output_file": "mental_health_conversations.parquet",
        "columns": None,
        "expected_row_count": 3512
    }
    
    DATASET_2 = {
        "name": "nbertagnolli/counsel-chat",
        "output_file": "counsel_chat.parquet",
        "columns": ["questionTitle", "questionText", "answerText"],
        "expected_row_count": None #will detetmine after download
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def download_dataset(self, dataset_name: str, columns: list = None) -> pd.DataFrame:
        logger.info(f"Downloading dataset: {dataset_name}")
        
        try:
            dataset = load_dataset(dataset_name, split="train")
            df = dataset.to_pandas()
            
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
        errors = []
        warnings = []
        
        if dataset_info["expected_row_count"]:
            if len(df) != dataset_info["expected_row_count"]:
                warnings.append(
                    f"Row count mismatch: expected {dataset_info['expected_row_count']}, "
                    f"got {len(df)}"
                )
        
        null_counts = df.isnull().sum()
        if null_counts.any():
            null_info = null_counts[null_counts > 0].to_dict()
            warnings.append(f"Null values found: {null_info}")
        
        for col in df.select_dtypes(include=['object']).columns:
            empty_count = (df[col].astype(str).str.strip() == "").sum()
            if empty_count > 0:
                warnings.append(f"Empty strings in {col}: {empty_count}")
        
        for warning in warnings:
            logger.warning(warning)
        
        for error in errors:
            logger.error(error)
        
        if errors:
            return False
        
        logger.info("Validation completed")
        return True
    
    def save_dataset(self, df: pd.DataFrame, filename: str) -> Path:
        output_path = self.output_dir / filename
        df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(df)} records to {output_path}")
        return output_path
    
    def download_and_save(self, dataset_info: dict, skip_existing: bool = True) -> Path:
        output_path = self.output_dir / dataset_info["output_file"]
        
        if skip_existing and output_path.exists():
            logger.info(f"Skipping {dataset_info['name']} - already exists at {output_path}")
            return output_path
        
        logger.info(f"Processing: {dataset_info['name']}")
        
        df = self.download_dataset(
            dataset_info["name"], 
            dataset_info["columns"]
        )
        
        if not self.validate_dataset(df, dataset_info):
            raise ValueError(f"Validation failed for {dataset_info['name']}")
        
        output_path = self.save_dataset(df, dataset_info["output_file"])
        
        return output_path
    
    def run(self, skip_existing: bool = True) -> dict:
        results = {}
        
        try:
            results["dataset_1"] = self.download_and_save(self.DATASET_1, skip_existing)
            results["dataset_2"] = self.download_and_save(self.DATASET_2, skip_existing)
            
            logger.info("All datasets downloaded successfully")
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

    downloader = DataDownloader(output_dir=output_dir)
    output_paths = downloader.run()
    
    print("Download complete")
    for dataset, path in output_paths.items():
        print(f"{dataset}: {path}")