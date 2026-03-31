## 2026-03-31

### Pipeline Orchestration
- Added `pipeline/flows.py` with four Prefect flows: `daily-ingest` (9:00 AM ET), `market-open-signals` (9:30 AM ET), `intraday-reeval` (11 AM / 1 PM / 3 PM ET), and `market-close-outcomes` (4:30 PM ET). All cron schedules target US Eastern market hours via UTC offsets.
- Added `pipeline/scheduler.py` as the local entry point: starts a Prefect server, waits for it to be healthy, then deploys all four flows with their cron schedules.
- Added `pipeline/run_pipeline.py` as a manual end-to-end runner that executes all pipeline stages sequentially without Prefect — useful for one-shot runs and local development.
- Resolved import path issues across `data/`, `signals/`, and `backtesting/` modules so all flows and the manual runner execute without `sys.path` hacks.
- `TRADING_DB_PATH` environment variable accepted by all flows; defaults to `data/trading.db` when unset.

### End-to-End Run
- Full pipeline executed on 2026-03-31 against the live SQLite database: data ingested for 46 of 50 universe tickers (4 likely delisted), 3 signals generated (AEIS, BOOT, CVCO), 0 resolved (all within hold window).
- Historical simulation across the 2-year OHLCV dataset produced 393 simulated signals: 50.4% win rate, +2.83% average return per signal, Sharpe ratio of 0.22.

### Model Performance Report
- Added `docs/model_performance_report.md` documenting v1 model methodology (8 technical features, logistic regression, 80/20 time-based split), backtesting approach, full simulation results, and five prioritized improvement areas (threshold tuning, ticker concentration cap, asymmetric exits, walk-forward validation, survivorship bias correction).

### Deployment Readiness
- All module imports now use package-relative paths; no `sys.path` manipulation required at runtime.
- `TRADING_DB_PATH` env var provides a clean override for the database path across all pipeline entry points.
- `backtesting/latest_backtest.json` is written at each `market-close-outcomes` run; initialized to zero values on a fresh database.
