import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime

from dashboard.utils.db import get_signals, get_outcomes, get_model_versions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _fetch_current_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    """Fetch the latest close price for each ticker via yfinance."""
    if not tickers:
        return {}
    import yfinance as yf
    prices: dict[str, float] = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty:
                prices[ticker] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return prices


def _recommendation(current: float | None, entry: float, target: float, stop: float) -> str:
    if current is None:
        return "N/A"
    if current >= target:
        return "At Target"
    if current >= target * 0.98:
        return "Near Target"
    if current <= stop:
        return "At Stop"
    if current <= stop * 1.02:
        return "Near Stop"
    return "Hold"


def _days_open(generated_at_str: str) -> int:
    try:
        dt = datetime.fromisoformat(str(generated_at_str))
        return (date.today() - dt.date()).days
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("Signal Generation")

# --- Summary banner ---
open_signals = get_signals(status="open")
all_signals = get_signals()
versions = get_model_versions()
latest_model = versions[-1].get("version", "unknown") if versions else "unknown"

n_open = len(open_signals)
active_tickers = sorted(open_signals["ticker"].unique().tolist()) if not open_signals.empty else []
avg_confidence = open_signals["confidence"].mean() if not open_signals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Open Signals", n_open)
col2.metric("Active Tickers", len(active_tickers))
col3.metric("Avg Confidence", f"{avg_confidence:.2f}" if n_open > 0 else "—")
col4.metric("Model in Use", latest_model)

st.divider()

# --- Open signals with recommendations ---
st.subheader("Open Signals")

if open_signals.empty:
    st.info("No active signals at this time.")
else:
    # Fetch current prices for open signal tickers
    tickers_tuple = tuple(active_tickers)
    with st.spinner("Fetching current prices..."):
        current_prices = _fetch_current_prices(tickers_tuple)

    rows = []
    for _, row in open_signals.iterrows():
        ticker = row["ticker"]
        entry = float(row.get("entry_price", 0) or 0)
        target = float(row.get("target_price", 0) or 0)
        stop = float(row.get("stop_loss", 0) or 0)
        current = current_prices.get(ticker)
        days_open = _days_open(str(row.get("generated_at", "")))

        rows.append({
            "Ticker":           ticker,
            "Entry Price":      round(entry, 2),
            "Target Price":     round(target, 2),
            "Stop Loss":        round(stop, 2),
            "Current Price":    round(current, 2) if current else "N/A",
            "Confidence":       round(float(row.get("confidence", 0) or 0), 3),
            "Hold (days)":      int(row.get("expected_hold_time", 10) or 10),
            "Days Open":        days_open,
            "Generated At":     str(row.get("generated_at", ""))[:10],
            "Recommendation":   _recommendation(current, entry, target, stop),
        })

    open_df = pd.DataFrame(rows)

    # Color-code recommendation column
    def _rec_color(val: str) -> str:
        colors = {
            "At Target":   "background-color: #27ae6040",
            "Near Target": "background-color: #2ecc7140",
            "At Stop":     "background-color: #e74c3c40",
            "Near Stop":   "background-color: #e67e2240",
            "Hold":        "",
            "N/A":         "",
        }
        return colors.get(val, "")

    styled = open_df.style.map(_rec_color, subset=["Recommendation"])
    st.dataframe(styled, width='stretch', hide_index=True)

st.divider()

# --- Past signal performance ---
st.subheader("Past Signal Performance")

outcomes_df = get_outcomes()

if outcomes_df.empty:
    # Fall back to closed signals without outcomes
    closed = all_signals[all_signals["status"] != "open"] if not all_signals.empty else pd.DataFrame()
    if closed.empty:
        st.info("No closed signals yet.")
    else:
        st.dataframe(
            closed[["ticker", "generated_at", "entry_price", "target_price", "stop_loss",
                    "confidence", "model_version"]].sort_values("generated_at", ascending=False),
            width='stretch',
            hide_index=True,
        )
else:
    # Performance table
    perf_cols = [c for c in ["ticker", "generated_at", "outcome", "pct_return", "exit_price"] if c in outcomes_df.columns]
    perf_df = outcomes_df[perf_cols].copy()
    if "pct_return" in perf_df.columns:
        perf_df["pct_return"] = perf_df["pct_return"].round(2)
    st.dataframe(perf_df.sort_values("generated_at", ascending=False), width='stretch', hide_index=True)

    # Summary stats
    total = len(outcomes_df)
    wins = (outcomes_df["outcome"] == "win").sum()
    losses = (outcomes_df["outcome"] == "loss").sum()
    neutrals = (outcomes_df["outcome"] == "neutral").sum()
    avg_ret = outcomes_df["pct_return"].mean() if "pct_return" in outcomes_df.columns else 0

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Closed", total)
    s2.metric("Win Rate", f"{wins / total:.1%}" if total > 0 else "—")
    s3.metric("Loss Rate", f"{losses / total:.1%}" if total > 0 else "—")
    s4.metric("Avg Return", f"{avg_ret:.2f}%" if total > 0 else "—")

    # Win rate by ticker bar chart
    if total > 0:
        ticker_stats = (
            outcomes_df.groupby("ticker")
            .apply(lambda g: pd.Series({
                "win_rate": (g["outcome"] == "win").mean(),
                "total":    len(g),
            }))
            .reset_index()
            .sort_values("win_rate", ascending=False)
        )
        fig = px.bar(
            ticker_stats,
            x="ticker",
            y="win_rate",
            title="Win Rate by Ticker",
            labels={"ticker": "Ticker", "win_rate": "Win Rate"},
            text_auto=".0%",
        )
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig, width='stretch')

st.divider()

# --- Signal schema (collapsed) ---
with st.expander("Signal Schema Reference"):
    schema = pd.DataFrame([
        {"Column": "id",                 "Type": "INTEGER", "Description": "Primary key"},
        {"Column": "ticker",             "Type": "TEXT",    "Description": "Stock symbol"},
        {"Column": "generated_at",       "Type": "TEXT",    "Description": "Timestamp when the signal was created"},
        {"Column": "signal_type",        "Type": "TEXT",    "Description": "BUY or SELL"},
        {"Column": "entry_price",        "Type": "REAL",    "Description": "Model's recommended entry price (last close at time of signal)"},
        {"Column": "target_price",       "Type": "REAL",    "Description": "entry x 1.05 -- 5% upside target"},
        {"Column": "stop_loss",          "Type": "REAL",    "Description": "entry x 0.97 -- 3% downside stop"},
        {"Column": "confidence",         "Type": "REAL",    "Description": "Model probability score (0 to 1); only signals >= 0.55 are kept"},
        {"Column": "model_version",      "Type": "TEXT",    "Description": "Version of the model that generated the signal"},
        {"Column": "status",             "Type": "TEXT",    "Description": "'open' (active) or 'closed'"},
        {"Column": "expected_hold_time", "Type": "INTEGER", "Description": "Expected holding period in trading days (10)"},
        {"Column": "notes",              "Type": "TEXT",    "Description": "Optional free-text notes"},
    ])
    st.dataframe(schema, width='stretch', hide_index=True)

    st.markdown("""
**Generation logic**

Each trading day at 9:30 AM ET, the signal generation flow runs the latest trained
model over all tickers in the universe. For each ticker, the most recent OHLCV row is
retrieved, features are computed, and the model outputs a probability that the stock
will be at least 3% higher in 10 trading days.

Only tickers where `confidence >= 0.55` produce a signal. For those tickers:

- **Entry price** = last adjusted close at generation time
- **Target price** = entry x 1.05 (5% upside)
- **Stop-loss** = entry x 0.97 (3% downside)
- **Expected hold time** = 10 trading days
""")
