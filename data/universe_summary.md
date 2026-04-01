# Ticker Universe Summary

## Source

- **ETF**: iShares Russell 2000 ETF (IWM) holdings CSV
- **URL**: https://www.ishares.com/us/products/239710/ishares-russell-2000-etf (public download)
- **Holdings date**: Mar 30, 2026
- **Generated**: 2026-04-01

## Selection Criteria

- **Index**: Russell 2000 constituents (via IWM holdings)
- **Market cap filter**: $300M–$2B (inclusive, using `yfinance` live data at generation time)
- **Ticker format**: Pure alphabetic only (no dots, dashes, or suffixes) — required by data schema
- **Exchange**: No additional exchange filter; IWM holds NYSE and NASDAQ names

## Rationale

IWM is a full-replication ETF tracking the Russell 2000 index. Downloading its holdings CSV from iShares gives a reliable, reproducible Russell 2000 constituent list without requiring a paid data provider. Market caps were fetched via the Yahoo Finance v7 quote API and used to filter the ~1,940-ticker IWM universe down to the $300M–$2B small-cap band. Tickers with non-alpha characters (e.g., BRK/B, BF.B) are excluded to match the project's ticker format constraint.

To preserve data continuity, tickers already present in the previous universe that remain within the $300M–$2B range were retained first. New tickers were added to fill up to the 150-ticker cap.

## Final Universe

- **Tickers in universe file**: 150
- **Market cap range at generation**: ~$303M – ~$2,000M
- **Carried over from previous universe**: 21 (still within $300M–$2B)
- **New tickers added**: 129
- **Removed from previous universe**: 29 (grew above $2B or fell below $300M)

Tickers removed from prior universe (no longer in $300M–$2B range):
AEIS, AMED, ANIK, ARCB, AROC, BANF, BCC, BCPC, BDC, BFAM, BOOT, BRC, CALC, CALF, CARG, CATS, CBT, CHEF, CHGG, CLAR, CNXC, COMM, COOP, CORT, CPRX, CRGY, CTRE, CURB, CVCO

## Data in SQLite

- **Table**: `market_data`
- **Target date range**: ~2 years of daily OHLCV ending 2026-04-01
- **Ingestion script**: `data/run_universe_ingest.py`

Tickers carried over from the prior universe retain their existing data rows. The 129 new tickers were ingested at generation time. Some tickers may return no data from yfinance (delisted, halted, or recently listed) — the ingestion layer handles these gracefully.

## Rebuilding

To regenerate this universe from scratch:

```bash
bash data/build_universe.sh
python -m data.run_universe_ingest
```

The build script downloads a fresh IWM holdings CSV, fetches current market caps from Yahoo Finance, and rewrites `tickers.json`. Re-running `run_universe_ingest` fetches OHLCV history for any new tickers.
