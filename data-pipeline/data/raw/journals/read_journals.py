#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

parquet_file = Path("data-pipeline/data/raw/journals/synthetic_journals.parquet")

if not parquet_file.exists():
    print(f"Error: File not found at {parquet_file}")
    exit(1)

df = pd.read_parquet(parquet_file)

print("SYNTHETIC JOURNALS DATA")
print(f"\nShape: {df.shape[0]} rows × {df.shape[1]} columns")
print(f"\nData Types:\n{df.dtypes}")
print(f"\nColumn Names:\n{list(df.columns)}")
print(f"\nFirst 5 rows:")
print(df.head())
print(f"\nBasic Statistics:")
print(df.describe(include='all'))
print(f"\nMissing Values:")
print(df.isnull().sum())

print(f"\nMemory Usage:")
print(df.memory_usage(deep=True))

