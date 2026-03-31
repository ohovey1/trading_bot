"""
Ingest 2 years of daily OHLCV data for the full ticker universe.

Run with: uv run python -m data.run_universe_ingest
"""
from pathlib import Path

from data.ingest import fetch_ohlcv
from data.normalize import normalize
from data.store import _DEFAULT_DB, store_market_data
from data.universe import load_universe


def main(db_path: str | None = None):
    db = db_path if db_path is not None else _DEFAULT_DB
    tickers = load_universe()
    print(f"Universe: {len(tickers)} tickers")

    tickers_with_data = 0
    total_rows = 0

    for ticker in tickers:
        raw = fetch_ohlcv([ticker], period="2y")
        if raw.empty:
            print(f"  {ticker}: no data")
            continue
        clean = normalize(raw)
        if clean.empty:
            print(f"  {ticker}: empty after normalization")
            continue
        inserted = store_market_data(clean, db_path=db)
        tickers_with_data += 1
        total_rows += inserted
        print(f"  {ticker}: {inserted} rows inserted")

    print(f"\nSummary:")
    print(f"  Tickers attempted:  {len(tickers)}")
    print(f"  Tickers with data:  {tickers_with_data}")
    print(f"  Total rows inserted: {total_rows}")


if __name__ == "__main__":
    main()
