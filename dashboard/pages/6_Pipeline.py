import streamlit as st
import pandas as pd

st.title("Pipeline & Orchestration")

# --- DAG diagram ---
st.subheader("Pipeline DAG")

st.markdown("""
```
daily_ingest_flow  (9:00 AM ET)
        |
        v
market_open_signals_flow  (9:30 AM ET)
        |
        v
intraday_reeval_flow  (11 AM / 1 PM / 3 PM ET)  <-- loops throughout day
        |
        v
market_close_outcomes_flow  (4:30 PM ET)
        |
        +---> updates backtesting/latest_backtest.json
        +---> closes outcomes table entries
```

Each flow is independent and can be run manually. Data flows downstream: ingest must
complete before signals can be generated; signals must exist before re-evaluation has
anything to resolve.
""")

# --- Schedule table ---
st.subheader("Schedule")

schedule = pd.DataFrame([
    {
        "Flow": "daily_ingest_flow",
        "Cron": "0 14 * * 1-5",
        "ET Time": "9:00 AM",
        "Description": "Fetch 2 years of OHLCV for all tickers and upsert into market_data",
    },
    {
        "Flow": "market_open_signals_flow",
        "Cron": "30 14 * * 1-5",
        "ET Time": "9:30 AM",
        "Description": "Run the latest model over all tickers; write buy signals for confidence >= 0.55",
    },
    {
        "Flow": "intraday_reeval_flow",
        "Cron": "0 16,18,20 * * 1-5",
        "ET Time": "11 AM / 1 PM / 3 PM",
        "Description": "Resolve open signals whose expected hold period has elapsed",
    },
    {
        "Flow": "market_close_outcomes_flow",
        "Cron": "30 21 * * 1-5",
        "ET Time": "4:30 PM",
        "Description": "Score all newly closed signals and update backtesting/latest_backtest.json",
    },
])

st.dataframe(schedule, use_container_width=True, hide_index=True)

# --- Re-evaluation loop ---
st.subheader("Re-evaluation Loop")

st.markdown("""
Open signals are checked three times per trading day. At each check, the system:

1. Queries all signals with `status = 'open'`
2. For each signal, calculates whether the expected hold time (10 trading days) has
   elapsed since `generated_at`
3. For matured signals, fetches the current close price and writes a row to the
   `outcomes` table with `outcome = win / loss / neutral` and `pct_return`
4. Updates the signal's `status` to `'closed'`

Signals that have not yet matured are left open and checked again at the next
re-evaluation window. This means a signal generated on Monday morning will be
eligible for resolution starting the following Monday at 11 AM ET.

The market close flow at 4:30 PM makes a final pass and also recomputes the aggregate
backtest metrics written to `backtesting/latest_backtest.json`. These metrics power
the summary cards on the Backtesting page.
""")

# --- How to run ---
st.subheader("How to Run")

st.markdown("**Start the full scheduler** (runs all flows on their cron schedule):")
st.code("uv run python -m pipeline.scheduler", language="bash")

st.markdown("**Run all flows once manually** (useful for testing or backfilling):")
st.code("uv run python -m pipeline.run_pipeline", language="bash")

st.markdown("**Run this dashboard:**")
st.code("uv run streamlit run dashboard/app.py", language="bash")

st.markdown("**Run the test suite:**")
st.code("uv run pytest tests/", language="bash")

# --- Environment notes ---
st.subheader("Environment Notes")
st.markdown("""
- All commands use `uv run` — never `pip install` or `python` directly.
- The scheduler process must stay running for cron-style execution. Use a process
  manager (e.g. `screen`, `tmux`, or a systemd service) to keep it alive.
- Prefect does not require a server for local scheduling — the flows run in-process
  on the machine where the scheduler is started.
- SQLite is used for all persistence. No external database setup is required.
  The database file lives at `data/trading.db` and is created automatically on
  first run.
""")
