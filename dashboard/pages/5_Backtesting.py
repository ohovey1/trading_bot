import streamlit as st
import pandas as pd
import plotly.express as px

from dashboard.utils.db import get_outcomes, get_backtest_summary, get_tickers

st.title("Backtesting & Results")

# --- How backtesting works ---
st.subheader("How Backtesting Works")

st.markdown("""
The backtest replays the trained model over historical OHLCV data to simulate every
buy signal it would have generated in the past. No live money is involved -- this is
purely a retrospective exercise to measure whether the model has predictive value.

**Simulated signal:** For each date in the historical dataset, the model scores each
ticker using only the data available up to that date. Any ticker where the model's
confidence score reaches 0.55 or higher generates a simulated buy signal at the
closing price on that date.

**Outcome determination:** Each simulated signal is resolved 10 trading days later
using the actual closing price. If the close on day 10 is 3% or more above the entry
price, the signal is a **win**. If it is more than 3% below, it is a **loss**.
Everything in between is **neutral**.

**Sharpe approximation:** The Sharpe ratio shown here is a rough estimate --
`mean(returns) / std(returns)` -- computed over all signal returns. It does not
annualize returns or use a risk-free rate. It is useful for comparing model versions
against each other, not for comparison to published fund metrics.

**Limitations to keep in mind:**

- No transaction costs or slippage are modeled. Every signal is assumed to execute at
  exactly the closing price.
- Signals are resolved at a fixed 10-day horizon regardless of whether the target or
  stop-loss was hit earlier.
- Look-ahead bias is prevented by computing features only from data available on the
  signal date, but survivorship bias may exist if delisted tickers are absent from the
  historical data.
""")

st.info(
    "Results shown for small-cap universe only ($300M-$2B market cap, "
    "sourced from Russell 2000 constituents).",
    icon="ℹ️",
)

st.divider()

# --- Load data ---
universe_tickers = set(get_tickers())

outcomes_df = get_outcomes()

# Filter to current universe tickers
if not outcomes_df.empty and universe_tickers:
    outcomes_df = outcomes_df[outcomes_df["ticker"].isin(universe_tickers)]

# Fall back to simulation if outcomes table is empty
if outcomes_df.empty:
    @st.cache_data
    def _run_simulation():
        from backtesting.simulate import simulate_historical_signals
        results = simulate_historical_signals()
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df = df.rename(columns={"signal_date": "resolved_at"})
        df["pct_return"] = df["pct_return"] * 100
        # Filter to universe
        if universe_tickers:
            df = df[df["ticker"].isin(universe_tickers)]
        return df

    outcomes_df = _run_simulation()

# --- Filters ---
with st.expander("Filters", expanded=False):
    all_tickers = sorted(outcomes_df["ticker"].unique().tolist()) if not outcomes_df.empty else []
    selected_tickers = st.multiselect("Tickers", all_tickers, default=all_tickers)

    if not outcomes_df.empty and "resolved_at" in outcomes_df.columns:
        dates = pd.to_datetime(outcomes_df["resolved_at"], errors="coerce").dropna()
        if len(dates) > 0:
            min_date = dates.min().date()
            max_date = dates.max().date()
            date_range = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        else:
            date_range = None
    else:
        date_range = None

    conf_threshold = st.slider("Min confidence", 0.50, 1.0, 0.55, step=0.01)

# Apply filters
filtered = outcomes_df.copy()
if not filtered.empty:
    if selected_tickers:
        filtered = filtered[filtered["ticker"].isin(selected_tickers)]
    if date_range and len(date_range) == 2 and "resolved_at" in filtered.columns:
        filtered["resolved_at"] = pd.to_datetime(filtered["resolved_at"], errors="coerce")
        filtered = filtered[
            (filtered["resolved_at"].dt.date >= date_range[0]) &
            (filtered["resolved_at"].dt.date <= date_range[1])
        ]
    if "confidence" in filtered.columns:
        filtered = filtered[filtered["confidence"] >= conf_threshold]

# --- Summary metrics ---
st.subheader("Summary Metrics")

st.markdown(
    "Aggregate performance across all simulated signals that pass the current filters. "
    "Win rate and Sharpe are the primary indicators of model quality."
)

backtest = get_backtest_summary()

if not filtered.empty:
    total = len(filtered)
    wins = (filtered["outcome"] == "win").sum()
    losses = (filtered["outcome"] == "loss").sum()
    win_rate = wins / total if total > 0 else 0
    loss_rate = losses / total if total > 0 else 0
    avg_return = filtered["pct_return"].mean() if "pct_return" in filtered.columns else 0

    returns = filtered["pct_return"].dropna() if "pct_return" in filtered.columns else pd.Series(dtype=float)
    sharpe = (returns.mean() / returns.std()) if len(returns) > 1 and returns.std() > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Signals", total)
    col2.metric("Win Rate", f"{win_rate:.1%}")
    col3.metric("Loss Rate", f"{loss_rate:.1%}")
    col4.metric("Avg Return", f"{avg_return:.2f}%")
    col5.metric("Sharpe (approx)", f"{sharpe:.2f}")
else:
    # Fall back to stored backtest JSON
    total = backtest.get("total_signals", 0)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Signals", total)
    col2.metric("Win Rate", f"{backtest.get('win_rate', 0):.1%}")
    col3.metric("Loss Rate", f"{backtest.get('loss_rate', 0):.1%}")
    col4.metric("Avg Return", f"{backtest.get('avg_pct_return', 0):.2f}%")
    col5.metric("Sharpe (approx)", f"{backtest.get('sharpe_approx', 0):.2f}")

if filtered.empty:
    st.info("No outcome data available. Run the pipeline to generate signals, or check backtesting/latest_backtest.json.")
    st.stop()

# --- Equity curve ---
st.subheader("Equity Curve")

st.markdown(
    "Hypothetical cumulative P&L if $1,000 were allocated to each signal at entry price, "
    "assuming every position was closed at the forward price 10 trading days later. "
    "No transaction costs or slippage are included."
)

if "resolved_at" in filtered.columns and "pct_return" in filtered.columns:
    eq = filtered.sort_values("resolved_at").copy()
    eq["trade_pnl"] = eq["pct_return"] / 100 * 1000
    eq["cumulative"] = eq["trade_pnl"].cumsum() + 1000
    fig_eq = px.line(
        eq,
        x="resolved_at",
        y="cumulative",
        title="Equity Curve ($1,000/signal)",
        labels={"resolved_at": "Date", "cumulative": "Portfolio Value ($)"},
    )
    st.plotly_chart(fig_eq, width='stretch')

# --- Win/loss/neutral pie + per-ticker win rate ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Outcome Distribution")
    st.markdown(
        "Breakdown of all filtered signals by outcome. Neutral signals "
        "returned between -3% and +3% over the 10-day hold period."
    )
    outcome_counts = filtered["outcome"].value_counts().reset_index()
    outcome_counts.columns = ["outcome", "count"]
    color_map = {"win": "#2ecc71", "loss": "#e74c3c", "neutral": "#95a5a6"}
    fig_pie = px.pie(
        outcome_counts,
        names="outcome",
        values="count",
        title="Win / Loss / Neutral",
        color="outcome",
        color_discrete_map=color_map,
    )
    st.plotly_chart(fig_pie, width='stretch')

with col_right:
    st.subheader("Win Rate by Ticker")
    st.markdown(
        "Win rate per ticker across all simulated signals. Tickers with very few "
        "signals (1-2 total) may show extreme win rates that are not meaningful."
    )
    ticker_stats = (
        filtered.groupby("ticker")
        .apply(lambda g: pd.Series({
            "win_rate": (g["outcome"] == "win").mean(),
            "total": len(g),
        }))
        .reset_index()
        .sort_values("win_rate", ascending=False)
    )
    fig_bar = px.bar(
        ticker_stats,
        x="ticker",
        y="win_rate",
        title="Win Rate per Ticker",
        labels={"ticker": "Ticker", "win_rate": "Win Rate"},
        text_auto=".0%",
    )
    fig_bar.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig_bar, width='stretch')

# --- Confidence vs. return scatter ---
st.subheader("Confidence vs. Return")

st.markdown(
    "Each point is one simulated signal. A well-calibrated model would show higher "
    "returns clustering at higher confidence scores. Flat or random dispersion "
    "indicates the confidence threshold needs tuning."
)

if "confidence" in filtered.columns and "pct_return" in filtered.columns:
    hover_cols = [c for c in ["ticker", "resolved_at"] if c in filtered.columns]
    fig_scatter = px.scatter(
        filtered,
        x="confidence",
        y="pct_return",
        color="outcome",
        color_discrete_map={"win": "#2ecc71", "loss": "#e74c3c", "neutral": "#95a5a6"},
        title="Confidence Score vs. Percent Return",
        labels={"confidence": "Confidence Score", "pct_return": "Return (%)"},
        hover_data=hover_cols,
    )
    fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_scatter, width='stretch')
