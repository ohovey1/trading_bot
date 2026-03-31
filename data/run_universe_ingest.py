"""
Ingest 2 years of daily OHLCV data for the full ticker universe.

Run with: uv run python -m data.run_universe_ingest
"""

from data.ingest import fetch_ohlcv
from data.normalize import normalize
from data.store import store_market_data
from data.universe import load_universe


def main():
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
        inserted = store_market_data(clean)
        tickers_with_data += 1
        total_rows += inserted
        print(f"  {ticker}: {inserted} rows inserted")

    print(f"\nSummary:")
    print(f"  Tickers attempted:  {len(tickers)}")
    print(f"  Tickers with data:  {tickers_with_data}")
    print(f"  Total rows inserted: {total_rows}")


if __name__ == "__main__":
    main()
