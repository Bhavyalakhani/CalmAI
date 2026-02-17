# tests for slicer.py
# covers slice_by_category, slice_by_numeric_bins, slice_by_keywords,
# slice_by_keyword_groups, compute_slice_stats, compute_all_slice_stats, apply_filter

import pytest
import pandas as pd
import numpy as np

from bias_detection.slicer import DataSlicer, SliceStats


@pytest.fixture
def sample_df():
    """small dataframe for slicing — mix of categories and numbers"""
    return pd.DataFrame({
        "category": ["A", "B", "A", "C", "B", "A"],
        "score": [10, 20, 30, 40, 50, 60],
        "text": [
            "feeling anxious today",
            "had a great day",
            "work stress and anxiety",
            "none of the keywords",
            "feeling happy and grateful",
            "anxious about the future",
        ],
    })


@pytest.fixture
def slicer(sample_df):
    return DataSlicer(sample_df)


# slice_by_category
class TestSliceByCategory:

    def test_splits_into_correct_groups(self, slicer):
        slices = slicer.slice_by_category("category")
        assert set(slices.keys()) == {"A", "B", "C"}
        assert len(slices["A"]) == 3
        assert len(slices["B"]) == 2
        assert len(slices["C"]) == 1

    def test_missing_column_returns_empty(self, slicer):
        slices = slicer.slice_by_category("nonexistent")
        assert slices == {}

    def test_handles_nan_values(self):
        # edge case: rows with nan category should be excluded
        df = pd.DataFrame({"cat": ["x", None, "x", "y"]})
        slicer = DataSlicer(df)
        slices = slicer.slice_by_category("cat")
        assert len(slices) == 2
        assert len(slices["x"]) == 2


# slice_by_numeric_bins
class TestSliceByNumericBins:

    def test_bins_data_correctly(self, slicer):
        slices = slicer.slice_by_numeric_bins("score", bins=[0, 25, 50, 100])
        # [0-25], (25-50], (50-100]
        assert len(slices) == 3
        # first bin: 10, 20 → 2 rows
        first_bin_key = list(slices.keys())[0]
        assert len(slices[first_bin_key]) == 2

    def test_custom_labels(self, slicer):
        slices = slicer.slice_by_numeric_bins("score", bins=[0, 30, 100], labels=["low", "high"])
        assert "low" in slices
        assert "high" in slices

    def test_missing_column_returns_empty(self, slicer):
        slices = slicer.slice_by_numeric_bins("nope", bins=[0, 50, 100])
        assert slices == {}


# slice_by_keywords
class TestSliceByKeywords:

    def test_matches_rows_with_keywords(self, slicer):
        result = slicer.slice_by_keywords("text", ["anxious", "anxiety"])
        assert len(result) == 3  # rows 0, 2, 5

    def test_case_insensitive_by_default(self, slicer):
        # "Anxious" with capital A should still match lowercase "anxious" in the data
        result = slicer.slice_by_keywords("text", ["Anxious"])
        assert len(result) == 2  # rows 0 and 5 contain "anxious"

    def test_missing_column_returns_empty_df(self, slicer):
        result = slicer.slice_by_keywords("nope", ["test"])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# slice_by_keyword_groups
class TestSliceByKeywordGroups:

    def test_groups_by_keyword_sets(self, slicer):
        groups = {
            "worry": ["anxious", "anxiety"],
            "positive": ["great", "happy", "grateful"],
        }
        slices = slicer.slice_by_keyword_groups("text", groups)
        assert "worry" in slices
        assert "positive" in slices
        assert len(slices["worry"]) == 3
        assert len(slices["positive"]) == 2


# compute_slice_stats
class TestComputeSliceStats:

    def test_computes_count_and_percentage(self, slicer, sample_df):
        subset = sample_df[sample_df["category"] == "A"]
        stats = slicer.compute_slice_stats(subset, "A")
        assert stats.count == 3
        assert stats.percentage == 50.0  # 3 out of 6

    def test_computes_numeric_stats_with_min_max(self, slicer, sample_df):
        subset = sample_df[sample_df["category"] == "A"]
        stats = slicer.compute_slice_stats(subset, "A", numeric_columns=["score"])
        assert "score_mean" in stats.numeric_stats
        assert "score_min" in stats.numeric_stats
        assert "score_max" in stats.numeric_stats
        assert stats.numeric_stats["score_min"] == 10.0
        assert stats.numeric_stats["score_max"] == 60.0

    def test_handles_empty_slice(self, slicer):
        empty = pd.DataFrame({"score": []})
        stats = slicer.compute_slice_stats(empty, "empty")
        assert stats.count == 0
        assert stats.percentage == 0.0


# compute_all_slice_stats
class TestComputeAllSliceStats:

    def test_returns_stats_for_each_slice(self, slicer):
        slices = slicer.slice_by_category("category")
        all_stats = slicer.compute_all_slice_stats(slices, numeric_columns=["score"])

        assert len(all_stats) == 3
        assert all(isinstance(s, SliceStats) for s in all_stats)
        names = {s.name for s in all_stats}
        assert "A" in names


# apply_filter
class TestApplyFilter:

    def test_filters_with_lambda(self, slicer):
        result = slicer.apply_filter(lambda df: df["score"] > 30)
        assert len(result) == 3  # 40, 50, 60

    def test_empty_result_on_impossible_filter(self, slicer):
        result = slicer.apply_filter(lambda df: df["score"] > 1000)
        assert len(result) == 0


# edge case: empty dataframe
class TestEmptyDataFrame:

    def test_slicer_on_zero_rows(self):
        df = pd.DataFrame({"category": [], "score": []})
        slicer = DataSlicer(df)
        assert slicer.slice_by_category("category") == {}
        stats = slicer.compute_slice_stats(df, "empty")
        assert stats.count == 0
        assert stats.percentage == 0.0
