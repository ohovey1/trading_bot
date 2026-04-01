import streamlit as st
import pandas as pd

from dashboard.utils.db import get_market_data, get_ticker_coverage, get_tickers

st.title("Data Layer")

# --- Data source ---
st.subheader("Data Source")
st.markdown("""
**Provider:** Yahoo Finance (`yfinance`)

Daily OHLCV bars are fetched for each ticker in the universe. Each row represents
one trading day and contains:

| Field | Description |
|-------|-------------|
| `open` | Opening price |
| `high` | Intraday high |
| `low` | Intraday low |
| `close` | Closing price (adjusted) |
| `volume` | Shares traded |
| `ingested_at` | Timestamp when the row was written to the database |

Data is stored in a SQLite database at `data/trading.db` in the `market_data` table.
Two years of history are fetched on every daily ingest run to keep the table current.
""")

# --- Ticker universe ---
st.subheader("Ticker Universe")

DELISTED = {"AMED", "CATS", "COMM", "COOP"}

coverage = get_ticker_coverage()
all_tickers = get_tickers()

if coverage.empty:
    st.warning("No coverage data found. Run the data ingestion pipeline first.")
else:
    # Merge coverage with full ticker list so delisted tickers show 0 rows
    full_df = pd.DataFrame({"ticker": all_tickers})
    merged = full_df.merge(coverage, on="ticker", how="left").fillna(
        {"row_count": 0, "min_date": "", "max_date": ""}
    )
    merged["row_count"] = merged["row_count"].astype(int)
    merged["delisted"] = merged["ticker"].isin(DELISTED)

    # Summary metrics
    active_tickers = merged[~merged["delisted"] & (merged["row_count"] > 0)]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickers", len(merged))
    col2.metric("Active Tickers", len(active_tickers))
    col3.metric("Total Rows", f"{merged['row_count'].sum():,}")
    if len(active_tickers) > 0:
        min_date = active_tickers["min_date"].min()
        max_date = active_tickers["max_date"].max()
        col4.metric("Date Range", f"{min_date} → {max_date}")

    # Coverage table
    display = merged.rename(columns={
        "ticker": "Ticker",
        "row_count": "Rows",
        "min_date": "First Date",
        "max_date": "Last Date",
        "delisted": "Delisted",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)

# --- Sample data preview ---
st.subheader("Sample Data Preview")

if coverage.empty or len(coverage) == 0:
    st.info("No market data available.")
else:
    active = coverage[~coverage["ticker"].isin(DELISTED) & (coverage["row_count"] > 0)]
    active_list = sorted(active["ticker"].tolist())
    if active_list:
        selected = st.selectbox("Select ticker", active_list)
        df = get_market_data(ticker=selected, limit=20)
        if df.empty:
            st.info(f"No data found for {selected}.")
        else:
            df = df.sort_values("date", ascending=False)
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = df[col].round(2)
            st.dataframe(df, use_container_width=True, hide_index=True)

# --- Data quality notes ---
st.subheader("Data Quality Notes")
st.markdown("""
- **Delisted tickers** — AMED, CATS, COMM, and COOP were in the original universe
  but are no longer trading. They return no data from Yahoo Finance and are excluded
  from feature engineering and signal generation.
- **Adjusted closes** — Yahoo Finance returns split- and dividend-adjusted close prices.
  All model features and signal prices are based on adjusted closes.
- **Missing days** — Market holidays and weekends produce no rows. The pipeline
  handles gaps naturally since features are computed on sorted date sequences per ticker.
- **Ingestion cadence** — The daily ingest flow fetches 2 years of history on each
  run, so any late-arriving corrections from Yahoo Finance are automatically backfilled.
- **Volume spikes** — The `volume_ratio` feature (today's volume / 20-day average)
  will be elevated around earnings announcements and index rebalancings. This is
  intentional — those events can carry predictive signal.
""")
