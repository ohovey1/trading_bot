"""
Tests for the data ingestion and normalization layer.
"""
import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data.ingest import fetch_ohlcv
from data.normalize import normalize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_yf_multiindex_df(tickers: list[str], n_days: int = 3) -> pd.DataFrame:
    """Build a DataFrame that mimics yfinance multi-ticker output."""
    dates = pd.date_range("2024-01-01", periods=n_days, name="Date")
    price_fields = ["Open", "High", "Low", "Close", "Volume"]
    cols = pd.MultiIndex.from_product([price_fields, tickers], names=["Price", "Ticker"])
    data = np.ones((n_days, len(cols))) * 100.0
    return pd.DataFrame(data, index=dates, columns=cols)


# ---------------------------------------------------------------------------
# fetch_ohlcv
# ---------------------------------------------------------------------------

def test_fetch_ohlcv_returns_correct_shape_and_columns():
    tickers = ["AAPL", "MSFT"]
    mock_raw = _make_yf_multiindex_df(tickers, n_days=3)

    with patch("yfinance.download", return_value=mock_raw):
        result = fetch_ohlcv(tickers)

    assert list(result.columns) == ["ticker", "date", "open", "high", "low", "close", "volume"]
    # 3 dates × 2 tickers = 6 rows
    assert len(result) == 6
    assert set(result["ticker"]) == {"AAPL", "MSFT"}


def test_fetch_ohlcv_warns_on_missing_ticker(caplog):
    # Only AAPL data returned — TSLA absent from columns
    mock_raw = _make_yf_multiindex_df(["AAPL"], n_days=3)

    with patch("yfinance.download", return_value=mock_raw):
        with caplog.at_level("WARNING", logger="data.ingest"):
            result = fetch_ohlcv(["AAPL", "TSLA"])

    assert "TSLA" in caplog.text
    # Only AAPL rows returned
    assert set(result["ticker"]) == {"AAPL"}


def test_fetch_ohlcv_returns_empty_df_on_no_data():
    with patch("yfinance.download", return_value=pd.DataFrame()):
        result = fetch_ohlcv(["FAKE"])

    assert result.empty
    assert list(result.columns) == ["ticker", "date", "open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

def test_normalize_drops_null_close_rows():
    df = pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL", "MSFT"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01"]),
            "open": [150.0, 151.0, 300.0],
            "high": [155.0, 156.0, 305.0],
            "low": [148.0, 149.0, 298.0],
            "close": [152.0, None, 302.0],  # second row should be dropped
            "volume": [1_000_000, 500_000, 200_000],
        }
    )
    result = normalize(df)
    assert len(result) == 2
    assert result["close"].notna().all()


def test_normalize_drops_zero_close_rows():
    df = pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "open": [150.0, 0.0],
            "high": [155.0, 0.0],
            "low": [148.0, 0.0],
            "close": [152.0, 0.0],  # zero close should be dropped
            "volume": [1_000_000, 0],
        }
    )
    result = normalize(df)
    assert len(result) == 1


def test_normalize_casts_numeric_columns_to_float64():
    df = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "date": pd.to_datetime(["2024-01-01"]),
            "open": [150],   # int
            "high": [155],
            "low": [148],
            "close": [152],
            "volume": [1_000_000],
        }
    )
    result = normalize(df)
    for col in ["open", "high", "low", "close", "volume"]:
        assert result[col].dtype == np.float64, f"{col} should be float64"


def test_normalize_date_is_datetime_date():
    df = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "date": pd.to_datetime(["2024-01-01"]),
            "open": [150.0],
            "high": [155.0],
            "low": [148.0],
            "close": [152.0],
            "volume": [1_000_000],
        }
    )
    result = normalize(df)
    assert isinstance(result["date"].iloc[0], datetime.date)
    assert not isinstance(result["date"].iloc[0], datetime.datetime)


def test_normalize_strips_timezone_from_date():
    df = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "date": pd.to_datetime(["2024-01-01"]).tz_localize("UTC"),
            "open": [150.0],
            "high": [155.0],
            "low": [148.0],
            "close": [152.0],
            "volume": [1_000_000],
        }
    )
    result = normalize(df)
    assert isinstance(result["date"].iloc[0], datetime.date)
