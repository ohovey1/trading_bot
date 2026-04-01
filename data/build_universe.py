"""
Build the ticker universe from IWM (iShares Russell 2000 ETF) holdings,
filtered to $300M–$2B market cap.

Usage:
    uv run python -m data.build_universe

Outputs:
    data/tickers.json  — updated ticker list
    Prints a summary table to stdout
"""
import io
import json
import re
import sqlite3
import time
from pathlib import Path

import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MARKET_CAP_MIN = 300_000_000
MARKET_CAP_MAX = 2_000_000_000
TARGET_MIN = 50
TARGET_MAX = 150

IWM_CSV_URL = (
    "https://www.ishares.com/us/products/239710/"
    "ishares-russell-2000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWM_holdings&dataType=fund"
)

_HERE = Path(__file__).parent
DB_PATH = _HERE / "trading.db"
TICKERS_JSON = _HERE / "tickers.json"

# Matches pure-alpha uppercase tickers only (required by test suite)
_TICKER_RE = re.compile(r"^[A-Z]+$")


# ---------------------------------------------------------------------------
# Step 1: Download IWM holdings
# ---------------------------------------------------------------------------

def fetch_iwm_tickers() -> list[str]:
    """Download IWM constituent list from iShares and return clean ticker symbols."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.ishares.com/",
    }
    print("Downloading IWM holdings from iShares...")
    resp = requests.get(IWM_CSV_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    # The CSV has a multi-line header before the data; find the actual column row.
    # iShares CSV format: first ~9 lines are fund metadata, then a blank line,
    # then the column headers, then data rows.
    text = resp.text
    lines = text.splitlines()

    # Find the line that starts with "Ticker" (the header row)
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Ticker"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not find 'Ticker' header row in IWM CSV")

    data_text = "\n".join(lines[header_idx:])
    import csv
    reader = csv.DictReader(io.StringIO(data_text))
    tickers = []
    for row in reader:
        ticker = row.get("Ticker", "").strip().upper()
        # Keep only pure-alpha tickers (no dots, dashes, or spaces)
        if ticker and _TICKER_RE.match(ticker):
            tickers.append(ticker)

    print(f"  {len(tickers)} pure-alpha tickers extracted from IWM holdings")
    return tickers


# ---------------------------------------------------------------------------
# Step 2: Get tickers already in the DB
# ---------------------------------------------------------------------------

def tickers_in_db() -> set[str]:
    """Return the set of tickers that have rows in the market_data table."""
    if not DB_PATH.exists():
        return set()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM market_data"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Step 3: Filter by market cap
# ---------------------------------------------------------------------------

def fetch_market_caps(tickers: list[str], batch_size: int = 50) -> dict[str, int | None]:
    """Fetch market cap for each ticker via yfinance. Returns {ticker: marketCap or None}."""
    caps: dict[str, int | None] = {}
    total = len(tickers)
    print(f"Fetching market caps for {total} tickers (batches of {batch_size})...")

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        print(f"  batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} "
              f"({len(batch)} tickers)...")
        for ticker in batch:
            try:
                info = yf.Ticker(ticker).fast_info
                cap = getattr(info, "market_cap", None)
                caps[ticker] = int(cap) if cap else None
            except Exception:
                caps[ticker] = None
        # Brief pause between batches to be polite to Yahoo Finance
        if i + batch_size < total:
            time.sleep(1)

    fetched = sum(1 for v in caps.values() if v is not None)
    print(f"  Market caps fetched: {fetched}/{total}")
    return caps


# ---------------------------------------------------------------------------
# Step 4: Select universe
# ---------------------------------------------------------------------------

def select_universe(
    candidates: list[str],
    caps: dict[str, int | None],
    existing_db: set[str],
) -> list[str]:
    """
    Filter to $300M–$2B market cap, prioritize DB-existing tickers,
    cap at TARGET_MAX.
    """
    in_range = [
        t for t in candidates
        if caps.get(t) is not None
        and MARKET_CAP_MIN <= caps[t] <= MARKET_CAP_MAX
    ]
    print(f"\nTickers in $300M–$2B range: {len(in_range)}")

    # Split into already-in-DB and new
    have_data = [t for t in in_range if t in existing_db]
    new_tickers = [t for t in in_range if t not in existing_db]

    print(f"  Already in DB:  {len(have_data)}")
    print(f"  New (no data):  {len(new_tickers)}")

    # Take all with data first, then fill up to TARGET_MAX with new ones
    universe = have_data[:]
    remaining_slots = TARGET_MAX - len(universe)
    if remaining_slots > 0:
        universe.extend(new_tickers[:remaining_slots])

    universe = sorted(set(universe))
    print(f"  Final universe: {len(universe)} tickers")
    return universe


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    candidates = fetch_iwm_tickers()
    existing_db = tickers_in_db()
    print(f"Tickers already in DB: {len(existing_db)}")

    caps = fetch_market_caps(candidates)

    universe = select_universe(candidates, caps, existing_db)

    if len(universe) < TARGET_MIN:
        print(
            f"WARNING: universe has only {len(universe)} tickers "
            f"(target minimum {TARGET_MIN}). "
            "Consider relaxing the market cap filter."
        )

    # Write tickers.json
    with open(TICKERS_JSON, "w") as f:
        json.dump(sorted(universe), f, indent=2)
    print(f"\nWrote {len(universe)} tickers to {TICKERS_JSON}")

    # Print summary stats
    in_range_caps = [caps[t] for t in universe if caps.get(t)]
    if in_range_caps:
        print(f"Market cap range in universe: "
              f"${min(in_range_caps):,.0f} – ${max(in_range_caps):,.0f}")

    return universe, caps


if __name__ == "__main__":
    main()
