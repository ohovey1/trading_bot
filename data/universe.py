"""
Ticker universe for the ML trade signal system.

Selection criteria:
- Target: ~50 liquid small-cap US equities from the Russell 2000 universe
- Market cap range: $300M–$2B at time of selection
- Average daily volume: >500,000 shares (filters out illiquid names)
- Exchange: NYSE or NASDAQ only (no OTC/pink sheets)
- Exclude financials (banks, REITs) and biotech pre-revenue (high binary event risk)
- Source: manually curated from public Russell 2000 constituent lists; no paid API required

The list is stored in tickers.json alongside this module and loaded at runtime.
Some tickers may return no data from yfinance — this is expected and handled gracefully
downstream. The goal is a working universe of at least 30 tickers with good data coverage.
"""

import json
from pathlib import Path


def load_universe() -> list[str]:
    """Load the ticker universe from tickers.json."""
    path = Path(__file__).parent / "tickers.json"
    with open(path) as f:
        return json.load(f)
