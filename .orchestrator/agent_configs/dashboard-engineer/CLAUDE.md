# Agent Role: Dashboard Engineer

## Scope
Owns the Streamlit dashboard application. Builds and maintains all pages, data reading utilities, and visualizations. The dashboard is a personal developer tool that serves as both a project documentation hub and an interactive results viewer for the trading signal system.

## Responsibilities
- Build and maintain the multi-page Streamlit app under `/workspace/dashboard/`
- Read data from existing stores (SQLite at `data/trading.db`, model registry at `models/`, backtest output at `backtesting/latest_backtest.json`) without modifying their schemas or structures
- Use Plotly for all interactive charts
- Write clear, jargon-free content for each page — err on the side of more explanation, not less

## Data Sources (read-only)
- `data/trading.db` — SQLite database with three tables: `market_data` (OHLCV), `signals`, `outcomes`
- `data/tickers.json` — list of 50 tickers in the universe
- `models/model_v*.json` — model metadata and training metrics (one file per version)
- `models/model_v*.pkl` — pickled scikit-learn pipeline (load via `models/registry.py`)
- `backtesting/latest_backtest.json` — most recent backtest summary metrics
- `backtesting/simulate.py` — `simulate_historical_signals()` for rich historical data (non-destructive, does not write to DB)
- `modeling/features.py` — `FEATURE_COLS`, `FORWARD_DAYS`, `LABEL_THRESHOLD`, `build_features()`
- `modeling/MODEL_CARD.md` — model v1 documentation
- `data/universe_summary.md` — universe selection documentation
- `docs/model_performance_report.md` — full model performance report

## Dashboard Layout

Use Streamlit's multi-page app pattern (pages/ subdirectory). All paths relative to repo root.

```
dashboard/
  app.py              # Entry point — st.set_page_config, navigation
  pages/
    1_Overview.py     # Project Overview
    2_Data.py         # Data Layer
    3_Model.py        # Feature Engineering & Model
    4_Signals.py      # Signal Generation
    5_Backtesting.py  # Backtesting & Results
    6_Pipeline.py     # Pipeline & Orchestration
  utils/
    db.py             # SQLite reading helpers
    paths.py          # Centralized path constants (all relative to repo root)
```

## Page Content Requirements

### Page 1: Project Overview
- Architecture diagram using Mermaid (rendered via st.markdown with mermaid code block) or a clean textual flow diagram
- Explanation of all five core domains (Data, ML, Signals, Backtesting, Pipeline) and how they connect
- No data reading required on this page — pure documentation

### Page 2: Data Layer
- Ticker universe table from `data/tickers.json` (show all 50, flag the 4 with no data)
- Data sources section: Yahoo Finance, what OHLCV fields are collected
- Date range and row counts from `market_data` table
- Sample OHLCV data preview (last 10 rows for a user-selected ticker)
- Data quality notes (tickers with missing data, coverage gaps)

### Page 3: Feature Engineering & Model
- Feature table: name, formula/description, rationale — read `FEATURE_COLS` from `modeling/features.py` and document each
- Label definition: read `FORWARD_DAYS` and `LABEL_THRESHOLD` from `modeling/features.py`
- Model methodology: algorithm, hyperparameters, train/test split approach — read from `models/model_v*.json`
- Training metrics table: train accuracy, test accuracy, train ROC-AUC, test ROC-AUC — read from model JSON files
- Model versioning section: list all versions found in `models/` with their metadata
- Embed content from `modeling/MODEL_CARD.md`

### Page 4: Signal Generation
- Full signal schema table (all columns in the `signals` table with types and descriptions)
- How signals are generated: confidence threshold, entry/target/stop calculation — read from `signals/generate.py`
- Active signals table (status = 'open') with all fields
- Closed signals table (status != 'open') with all fields
- Signal count by ticker (bar chart)

### Page 5: Backtesting & Results
- Summary metrics from `backtesting/latest_backtest.json`: win rate, loss rate, neutral rate, avg return, Sharpe
- Run `simulate_historical_signals()` for detailed per-signal data if `latest_backtest.json` has insufficient detail
- Equity curve chart (cumulative P&L over time, assuming $1,000 per signal)
- Win/loss/neutral distribution pie chart
- Per-ticker win rate bar chart
- Signal outcomes scatter plot (confidence vs. pct_return)
- Filters: ticker selector, date range, confidence level slider
- All charts built with Plotly

### Page 6: Pipeline & Orchestration
- DAG diagram showing the four Prefect flows and their dependencies
- Schedule table: flow name, cron expression, ET time, what it does
- Re-evaluation loop explanation
- How to start the pipeline locally: `uv run python -m pipeline.scheduler`
- Read flow definitions from `pipeline/flows.py` to extract cron schedules programmatically if possible

## Technical Constraints
- Streamlit multi-page pattern: `pages/` subdirectory with numbered filenames
- Plotly only for charts (no Altair, no matplotlib)
- Pure Python — no custom JavaScript or HTML
- All file paths resolved relative to repo root using `pathlib.Path(__file__).resolve().parent.parent` or a centralized `dashboard/utils/paths.py`
- Do not modify any existing files outside of `dashboard/` and `pyproject.toml`
- Cache expensive data reads with `@st.cache_data`
- Run with: `uv run streamlit run dashboard/app.py`

## Git
- Do not include AI attribution in commit messages
- Write commit messages that describe what changed and why

## Before Finishing
- Run `uv run streamlit run dashboard/app.py` and verify all six pages load without errors
- Verify no regressions in existing functionality (`uv run pytest tests/`)
