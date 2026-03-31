"""
Smoke-test ingestion run: fetch, normalize, and store OHLCV data.

Usage:
    python -m data.run_ingest
"""
from data.ingest import fetch_ohlcv
from data.normalize import normalize
from data.store import store_market_data

TICKERS = ["AAPL", "MSFT", "TSLA"]


if __name__ == "__main__":
    df = fetch_ohlcv(TICKERS)
    df = normalize(df)
    inserted = store_market_data(df)
    print(f"Fetched {len(df)} rows, inserted {inserted} new rows.")
