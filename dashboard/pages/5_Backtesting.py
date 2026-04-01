import streamlit as st
import pandas as pd
import plotly.express as px

from dashboard.utils.db import get_outcomes, get_backtest_summary

st.title("Backtesting & Results")

# --- Load data ---
outcomes_df = get_outcomes()

# Fall back to simulation if outcomes table is empty
if outcomes_df.empty:
    @st.cache_data
    def _run_simulation():
        from backtesting.simulate import simulate_historical_signals
        results = simulate_historical_signals()
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df = df.rename(columns={
            "signal_date": "resolved_at",
        })
        df["pct_return"] = df["pct_return"] * 100
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
st.subheader("Equity Curve ($1,000/signal)")

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
    st.plotly_chart(fig_eq, use_container_width=True)

# --- Win/loss/neutral pie ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Outcome Distribution")
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
    st.plotly_chart(fig_pie, use_container_width=True)

# --- Per-ticker win rate bar ---
with col_right:
    st.subheader("Win Rate by Ticker")
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
    st.plotly_chart(fig_bar, use_container_width=True)

# --- Confidence vs. return scatter ---
st.subheader("Confidence vs. Return")

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
    st.plotly_chart(fig_scatter, use_container_width=True)
