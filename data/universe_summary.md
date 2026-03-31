# Phase 1 Universe Summary — Handoff to ml-engineer

## Selection Criteria

- ~50 liquid small-cap US equities from the Russell 2000 universe
- Market cap range: $300M–$2B at time of curation
- Average daily volume: >500,000 shares
- Exchange: NYSE or NASDAQ only (no OTC/pink sheets)
- Excluded: financials (banks, REITs), pre-revenue biotech (high binary event risk)
- Source: manually curated from public Russell 2000 constituent lists

## Final Universe

- **Tickers in universe file:** 50
- **Tickers with data:** 46 (92%)
- **Tickers flagged insufficient (<200 rows):** 4 (AMED, CATS, COMM, COOP — all returned no data from yfinance, likely delisted or unavailable)

## Data in SQLite

- **Table:** `market_data`
- **Date range:** 2024-04-01 to 2026-03-30 (~2 years of daily OHLCV)
- **Total rows:** 22,922
- **Rows per ticker (active):** 377–501 (CURB listed ~Sep 2024; all others have 501 rows)
- **Data gaps:** 0 gaps ≥7 calendar days for any ticker

## Tickers Dropped

None dropped — 4/50 (8%) are insufficient, below the 20% threshold. They are present in `tickers.json` but contribute no rows to `market_data`. Downstream code should handle missing tickers gracefully (the ingestion layer already does).

Tickers with no data: AMED, CATS, COMM, COOP

## What's Available for Modeling

All 46 active tickers have 377–501 rows of clean daily OHLCV data covering approximately 2024-04-01 through 2026-03-30. This is sufficient for feature engineering (technical indicators, rolling windows) and training a baseline classifier.

The `data/universe.py` module exposes `load_universe()` which returns all 50 tickers from `data/tickers.json`. Filter against `market_data` for the active set.
