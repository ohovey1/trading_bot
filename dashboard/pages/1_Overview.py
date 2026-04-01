import streamlit as st

st.title("Project Overview")

st.markdown("""
This system ingests daily OHLCV data for a 50-ticker Russell 2000 universe, engineers
technical features, trains a logistic regression classifier, generates trade signals
with entry/target/stop prices, re-evaluates open positions intraday, and automatically
tracks outcomes — no manual labeling required.
""")

st.subheader("Architecture")

st.markdown("""
```mermaid
graph LR
    A[Data Ingestion] --> B[Feature Engineering]
    B --> C[ML Model]
    C --> D[Signal Generation]
    D --> E[Open Signals]
    E --> F[Re-evaluation Loop]
    F --> G[Outcome Tracking]
    G --> H[Backtesting]
    H --> C
```
""")

st.subheader("System Domains")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Data**")
    st.markdown("""
Yahoo Finance is the primary data source. Daily OHLCV bars (open, high, low, close,
volume) are fetched for a 50-ticker subset of the Russell 2000 small-cap index and
stored in a SQLite database. The ingestion layer is designed so the data provider
can be swapped (e.g. Polygon.io, Tiingo) with minimal friction.
    """)

    st.markdown("**ML Model**")
    st.markdown("""
A logistic regression classifier serves as the intentionally minimal baseline. It
ingests 8 technical features derived from OHLCV data and outputs a probability that
the stock will be at least 3% higher 10 trading days from now. The model is versioned
and reproducible — complexity is added only after the baseline is validated.
    """)

    st.markdown("**Signals**")
    st.markdown("""
A buy signal is generated whenever the model's confidence score meets or exceeds 0.55.
Each signal carries an entry price (last close), a 5% upside target, a 3% downside
stop-loss, an expected hold time of 10 trading days, and the model version that
produced it.
    """)

with col2:
    st.markdown("**Backtesting**")
    st.markdown("""
The backtesting layer replays the model over historical OHLCV data, simulates every
signal it would have generated, and resolves each one using the actual close price
10 trading days later. Outcomes are classified win/loss/neutral based on whether the
return exceeded ±3%. This bootstraps performance metrics before live signals accumulate.
    """)

    st.markdown("**Pipeline**")
    st.markdown("""
Four Prefect flows run on a Monday–Friday schedule. Data ingestion fires at market
open, signal generation runs at 9:30 AM ET, intraday re-evaluation checks open
positions at 11 AM / 1 PM / 3 PM ET, and a closing flow scores outcomes at 4:30 PM ET.
The pipeline is designed to run unattended — no human intervention is needed during
the trading day.
    """)

st.subheader("End-to-End Flow")

st.markdown("""
Each trading day begins with a data pull that refreshes up to two years of OHLCV
history for every ticker in the universe. Feature engineering runs on the latest
data to produce the 8 model inputs. The model scores each ticker and emits buy signals
for any that clear the confidence threshold, recording entry, target, stop-loss, and
expected hold time in the database.

Throughout the day, the re-evaluation loop checks every open signal whose hold period
has elapsed. When a signal matures, the current price is compared to the entry price
and the position is closed as a win, loss, or neutral. At market close, a final pass
scores all newly closed signals, updates aggregate metrics, and writes a fresh backtest
summary that will be reflected in the dashboard the next morning.

This loop runs continuously without manual intervention. The only human touchpoint is
reviewing the dashboard to understand how the system is performing and deciding when
to retrain the model.
""")
