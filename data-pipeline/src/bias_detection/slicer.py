from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

import pandas as pd
import numpy as np


@dataclass
class SliceStats:
    name: str
    count: int
    percentage: float
    numeric_stats: Dict[str, float]


class DataSlicer:
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.total_count = len(df)
    
    def slice_by_category(self, column: str) -> Dict[str, pd.DataFrame]:
        if column not in self.df.columns:
            return {}
        
        slices = {}
        for value in self.df[column].dropna().unique():
            slices[str(value)] = self.df[self.df[column] == value]
        
        return slices
    
    def slice_by_numeric_bins(self, column: str, bins: List[float], 
                             labels: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        if column not in self.df.columns:
            return {}
        
        if labels is None:
            labels = [f"{bins[i]}-{bins[i+1]}" for i in range(len(bins)-1)]
        
        self.df["_bin"] = pd.cut(self.df[column], bins=bins, labels=labels, include_lowest=True)
        
        slices = {}
        for label in labels:
            slices[label] = self.df[self.df["_bin"] == label].drop(columns=["_bin"])
        
        self.df = self.df.drop(columns=["_bin"])
        return slices
    
    def slice_by_keywords(self, column: str, keywords: List[str], 
                         case_sensitive: bool = False) -> pd.DataFrame:
        if column not in self.df.columns:
            return pd.DataFrame()
        
        pattern = "|".join(keywords)
        flags = 0 if case_sensitive else pd.Series.str.contains.__code__.co_varnames
        
        mask = self.df[column].str.contains(pattern, case=case_sensitive, na=False)
        return self.df[mask]
    
    def slice_by_keyword_groups(self, column: str, 
                                keyword_groups: Dict[str, List[str]],
                                case_sensitive: bool = False) -> Dict[str, pd.DataFrame]:
        slices = {}
        for group_name, keywords in keyword_groups.items():
            slices[group_name] = self.slice_by_keywords(column, keywords, case_sensitive)
        return slices
    
    def compute_slice_stats(self, slice_df: pd.DataFrame, slice_name: str,
                           numeric_columns: Optional[List[str]] = None) -> SliceStats:
        count = len(slice_df)
        percentage = (count / self.total_count * 100) if self.total_count > 0 else 0
        
        numeric_stats = {}
        if numeric_columns:
            for col in numeric_columns:
                if col in slice_df.columns:
                    numeric_stats[f"{col}_mean"] = float(slice_df[col].mean())
                    numeric_stats[f"{col}_std"] = float(slice_df[col].std())
                    numeric_stats[f"{col}_median"] = float(slice_df[col].median())
        
        return SliceStats(
            name=slice_name,
            count=count,
            percentage=round(percentage, 2),
            numeric_stats=numeric_stats
        )
    
    def compute_all_slice_stats(self, slices: Dict[str, pd.DataFrame],
                                numeric_columns: Optional[List[str]] = None) -> List[SliceStats]:
        stats = []
        for name, slice_df in slices.items():
            stats.append(self.compute_slice_stats(slice_df, name, numeric_columns))
        return stats
    
    def apply_filter(self, condition: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
        mask = condition(self.df)
        return self.df[mask]
