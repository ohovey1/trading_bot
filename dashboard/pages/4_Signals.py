import streamlit as st
import pandas as pd
import plotly.express as px

from dashboard.utils.db import get_signals

st.title("Signal Generation")

# --- Signal schema ---
st.subheader("Signal Schema")

schema = pd.DataFrame([
    {"Column": "id",                "Type": "INTEGER", "Description": "Primary key"},
    {"Column": "ticker",            "Type": "TEXT",    "Description": "Stock symbol"},
    {"Column": "generated_at",      "Type": "TEXT",    "Description": "Timestamp when the signal was created"},
    {"Column": "signal_type",       "Type": "TEXT",    "Description": "BUY or SELL"},
    {"Column": "entry_price",       "Type": "REAL",    "Description": "Model's recommended entry price (last close at time of signal)"},
    {"Column": "target_price",      "Type": "REAL",    "Description": "entry × 1.05 — 5% upside target"},
    {"Column": "stop_loss",         "Type": "REAL",    "Description": "entry × 0.97 — 3% downside stop"},
    {"Column": "confidence",        "Type": "REAL",    "Description": "Model probability score (0 to 1); only signals >= 0.55 are kept"},
    {"Column": "model_version",     "Type": "TEXT",    "Description": "Version of the model that generated the signal"},
    {"Column": "status",            "Type": "TEXT",    "Description": "'open' (active) or 'closed'"},
    {"Column": "expected_hold_time","Type": "INTEGER", "Description": "Expected holding period in trading days (10)"},
    {"Column": "notes",             "Type": "TEXT",    "Description": "Optional free-text notes"},
])

st.dataframe(schema, use_container_width=True, hide_index=True)

# --- Generation logic ---
st.subheader("Generation Logic")
st.markdown("""
Each trading day at 9:30 AM ET, the signal generation flow runs the latest trained
model over all tickers in the universe. For each ticker, the most recent OHLCV row is
retrieved, features are computed, and the model outputs a probability that the stock
will be ≥3% higher in 10 trading days.

Only tickers where `confidence >= 0.55` produce a signal. For those tickers:

- **Entry price** = last adjusted close at generation time
- **Target price** = entry × 1.05 (5% upside)
- **Stop-loss** = entry × 0.97 (3% downside)
- **Expected hold time** = 10 trading days

Signals are written to the `signals` table with `status = 'open'`. The intraday
re-evaluation flow checks open signals multiple times per day and closes any whose
hold period has elapsed, recording the exit price in the `outcomes` table.
""")

# --- Active signals ---
st.subheader("Active Signals")

open_signals = get_signals(status="open")
if open_signals.empty:
    st.info("No active signals at this time.")
else:
    st.dataframe(open_signals, use_container_width=True, hide_index=True)

# --- Closed signals ---
st.subheader("Closed Signals")

all_signals = get_signals()
closed = all_signals[all_signals["status"] != "open"] if not all_signals.empty else pd.DataFrame()

if closed.empty:
    st.info("No closed signals yet.")
else:
    st.dataframe(closed.sort_values("generated_at", ascending=False), use_container_width=True, hide_index=True)

# --- Signal count by ticker bar chart ---
st.subheader("Signal Count by Ticker")

if all_signals.empty:
    st.info("No signals in the database yet.")
else:
    counts = (
        all_signals.groupby("ticker")
        .size()
        .reset_index(name="count")
        .sort_values("count")
    )
    fig = px.bar(
        counts,
        x="count",
        y="ticker",
        orientation="h",
        title="Total Signals per Ticker",
        labels={"count": "Signal Count", "ticker": "Ticker"},
    )
    fig.update_layout(height=max(300, len(counts) * 20))
    st.plotly_chart(fig, use_container_width=True)
