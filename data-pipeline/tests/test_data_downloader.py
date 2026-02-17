# tests for data_downloader.py
# covers downloading from huggingface, column filtering, validation, saving, and skip-existing logic

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch

from acquisition.data_downloader import DataDownloader


@pytest.fixture
def downloader(tmp_path):
    return DataDownloader(output_dir=tmp_path)


@pytest.fixture
def simple_df():
    return pd.DataFrame({"col1": ["a", "b", "c"], "col2": [1, 2, 3]})


# init
class TestInit:

    def test_creates_output_directory(self, tmp_path):
        out = tmp_path / "new_dir"
        dl = DataDownloader(output_dir=out)
        assert out.exists()
        assert dl.output_dir == out

    def test_defaults_to_data_raw(self):
        # just make sure it doesn't crash when no arg is given
        dl = DataDownloader()
        assert dl.output_dir == Path("data/raw")


# download
class TestDownload:

    @patch("acquisition.data_downloader.load_dataset")
    def test_returns_dataframe(self, mock_load, downloader):
        mock_ds = Mock()
        mock_ds.to_pandas.return_value = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        mock_load.return_value = mock_ds

        df = downloader.download_dataset("test/dataset")

        assert len(df) == 2
        mock_load.assert_called_once_with("test/dataset", split="train")

    @patch("acquisition.data_downloader.load_dataset")
    def test_filters_to_requested_columns(self, mock_load, downloader):
        mock_ds = Mock()
        mock_ds.to_pandas.return_value = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        mock_load.return_value = mock_ds

        df = downloader.download_dataset("test/dataset", columns=["a", "c"])
        assert list(df.columns) == ["a", "c"]

    @patch("acquisition.data_downloader.load_dataset")
    def test_raises_on_missing_columns(self, mock_load, downloader):
        mock_ds = Mock()
        mock_ds.to_pandas.return_value = pd.DataFrame({"a": [1]})
        mock_load.return_value = mock_ds

        with pytest.raises(ValueError, match="Missing required columns"):
            downloader.download_dataset("test/dataset", columns=["a", "nope"])

    @patch("acquisition.data_downloader.load_dataset")
    def test_empty_dataset(self, mock_load, downloader):
        # edge case: huggingface returns zero rows
        mock_ds = Mock()
        mock_ds.to_pandas.return_value = pd.DataFrame({"a": [], "b": []})
        mock_load.return_value = mock_ds

        df = downloader.download_dataset("test/empty")
        assert len(df) == 0


# validation
class TestValidation:

    def test_passes_on_clean_data(self, downloader, simple_df):
        info = {"expected_row_count": 3, "name": "test"}
        assert downloader.validate_dataset(simple_df, info) is True

    def test_warns_on_row_count_mismatch(self, downloader, simple_df):
        # row count mismatch is a warning, not an error — should still pass
        info = {"expected_row_count": 999, "name": "test"}
        assert downloader.validate_dataset(simple_df, info) is True

    def test_warns_on_null_values(self, downloader):
        df = pd.DataFrame({"a": [1, None, 3]})
        info = {"expected_row_count": None, "name": "test"}
        assert downloader.validate_dataset(df, info) is True

    def test_handles_all_null_column(self, downloader):
        # edge case: entire column is null
        df = pd.DataFrame({"a": [None, None, None]})
        info = {"expected_row_count": None, "name": "test"}
        assert downloader.validate_dataset(df, info) is True


# save
class TestSave:

    def test_roundtrips_through_parquet(self, downloader, simple_df):
        path = downloader.save_dataset(simple_df, "out.parquet")
        assert path.exists()
        loaded = pd.read_parquet(path)
        pd.testing.assert_frame_equal(loaded, simple_df)

    def test_can_save_empty_dataframe(self, downloader):
        # edge case: nothing to save
        df = pd.DataFrame({"a": [], "b": []})
        path = downloader.save_dataset(df, "empty.parquet")
        assert path.exists()


# download_and_save
class TestDownloadAndSave:

    @patch.object(DataDownloader, "download_dataset")
    def test_skips_existing_file(self, mock_dl, downloader):
        info = DataDownloader.DATASET_1
        existing = downloader.output_dir / info["output_file"]
        existing.touch()

        result = downloader.download_and_save(info, skip_existing=True)

        assert result == existing
        mock_dl.assert_not_called()

    @patch.object(DataDownloader, "save_dataset", return_value=Path("out.parquet"))
    @patch.object(DataDownloader, "validate_dataset", return_value=True)
    @patch.object(DataDownloader, "download_dataset")
    def test_downloads_validates_saves(self, mock_dl, mock_val, mock_save, downloader, simple_df):
        mock_dl.return_value = simple_df
        info = DataDownloader.DATASET_1

        downloader.download_and_save(info, skip_existing=False)

        mock_dl.assert_called_once()
        mock_val.assert_called_once()
        mock_save.assert_called_once()
