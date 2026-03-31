"""
Normalizes raw OHLCV DataFrames before storage.
"""
import datetime

import pandas as pd


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize a raw OHLCV DataFrame.

    - Drops rows where close is null or zero
    - Casts numeric columns to float64
    - Ensures date column is datetime.date (strips timezone if present)
    """
    df = df.copy()

    # Drop rows with missing or zero close price
    df = df[df["close"].notna() & (df["close"] != 0)]

    # Cast numeric columns to float64
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype("float64")

    # Ensure date is datetime.date (not a tz-aware Timestamp or datetime64)
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        if df["date"].dt.tz is not None:
            df["date"] = df["date"].dt.tz_convert(None)
        df["date"] = df["date"].dt.date
    elif not isinstance(df["date"].iloc[0], datetime.date):
        df["date"] = pd.to_datetime(df["date"]).dt.date

    return df.reset_index(drop=True)
