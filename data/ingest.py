"""
Fetches raw OHLCV market data from Yahoo Finance.
"""
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_ohlcv(
    tickers: list[str],
    period: str = "6mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLCV data for the given tickers from Yahoo Finance.

    Returns a DataFrame with columns: ticker, date, open, high, low, close, volume.
    Logs a warning for any ticker with missing data but does not raise.
    """
    raw = yf.download(
        tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=True,
        timeout=30,  # prevent indefinite hang if Yahoo Finance is unresponsive
    )

    if raw.empty:
        logger.warning("yfinance returned no data for tickers: %s", tickers)
        return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume"])

    # yfinance returns MultiIndex columns when downloading multiple tickers:
    #   level 0 = price type (Open, High, Low, Close, Volume)
    #   level 1 = ticker symbol
    if isinstance(raw.columns, pd.MultiIndex):
        frames = []
        available = set(raw.columns.get_level_values(1).unique())
        for ticker in tickers:
            if ticker not in available:
                logger.warning("No data returned for ticker: %s", ticker)
                continue
            ticker_df = raw.xs(ticker, axis=1, level=1).copy()
            ticker_df = ticker_df.reset_index()
            ticker_df.insert(0, "ticker", ticker)
            frames.append(ticker_df)

        if not frames:
            return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume"])
        df = pd.concat(frames, ignore_index=True)
    else:
        # Single ticker returns flat columns
        df = raw.reset_index()
        df.insert(0, "ticker", tickers[0])

    # Normalize column names to lowercase
    df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]

    # yfinance uses 'datetime' for intraday intervals, 'date' for daily
    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "date"})

    return df[["ticker", "date", "open", "high", "low", "close", "volume"]]
