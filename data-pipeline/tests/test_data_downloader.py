import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from acquisition.data_downloader import DataDownloader


@pytest.fixture
def downloader(tmp_path):
    return DataDownloader(output_dir=tmp_path)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'col1': ['a', 'b', 'c'],
        'col2': [1, 2, 3]
    })


class TestDataDownloader:
    
    def test_init_creates_directory(self, tmp_path):
        output_dir = tmp_path / "test_output"
        downloader = DataDownloader(output_dir=output_dir)
        assert output_dir.exists()
        assert downloader.output_dir == output_dir
    
    @patch('acquisition.data_downloader.load_dataset')
    def test_download_dataset_success(self, mock_load, downloader):
        mock_dataset = Mock()
        mock_dataset.to_pandas.return_value = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        mock_load.return_value = mock_dataset
        
        df = downloader.download_dataset("test/dataset")
        
        assert len(df) == 2
        assert list(df.columns) == ['a', 'b']
        mock_load.assert_called_once_with("test/dataset", split="train")
    
    @patch('acquisition.data_downloader.load_dataset')
    def test_download_dataset_with_columns(self, mock_load, downloader):
        mock_dataset = Mock()
        mock_dataset.to_pandas.return_value = pd.DataFrame({
            'a': [1, 2], 'b': [3, 4], 'c': [5, 6]
        })
        mock_load.return_value = mock_dataset
        
        df = downloader.download_dataset("test/dataset", columns=['a', 'c'])
        
        assert list(df.columns) == ['a', 'c']
    
    @patch('acquisition.data_downloader.load_dataset')
    def test_download_dataset_missing_columns(self, mock_load, downloader):
        mock_dataset = Mock()
        mock_dataset.to_pandas.return_value = pd.DataFrame({'a': [1, 2]})
        mock_load.return_value = mock_dataset
        
        with pytest.raises(ValueError, match="Missing required columns"):
            downloader.download_dataset("test/dataset", columns=['a', 'missing'])
    
    def test_validate_dataset_row_count_warning(self, downloader, sample_df):
        dataset_info = {"expected_row_count": 5, "name": "test"}
        
        result = downloader.validate_dataset(sample_df, dataset_info)
        
        assert result is True
    
    def test_validate_dataset_null_values(self, downloader):
        df = pd.DataFrame({'a': [1, None, 3]})
        dataset_info = {"expected_row_count": None, "name": "test"}
        
        result = downloader.validate_dataset(df, dataset_info)
        
        assert result is True
    
    def test_save_dataset(self, downloader, sample_df):
        path = downloader.save_dataset(sample_df, "test.parquet")
        
        assert path.exists()
        loaded_df = pd.read_parquet(path)
        pd.testing.assert_frame_equal(loaded_df, sample_df)
    
    @patch.object(DataDownloader, 'download_dataset')
    @patch.object(DataDownloader, 'validate_dataset')
    def test_download_and_save_skip_existing(self, mock_validate, mock_download, downloader):
        dataset_info = DataDownloader.DATASET_1
        existing_file = downloader.output_dir / dataset_info["output_file"]
        existing_file.touch()
        
        result = downloader.download_and_save(dataset_info, skip_existing=True)
        
        assert result == existing_file
        mock_download.assert_not_called()
    
    @patch.object(DataDownloader, 'download_dataset')
    @patch.object(DataDownloader, 'validate_dataset', return_value=True)
    @patch.object(DataDownloader, 'save_dataset')
    def test_download_and_save_new_file(self, mock_save, mock_validate, 
                                        mock_download, downloader, sample_df):
        mock_download.return_value = sample_df
        mock_save.return_value = Path("output.parquet")
        dataset_info = DataDownloader.DATASET_1
        
        result = downloader.download_and_save(dataset_info, skip_existing=False)
        
        mock_download.assert_called_once()
        mock_validate.assert_called_once()
        mock_save.assert_called_once()