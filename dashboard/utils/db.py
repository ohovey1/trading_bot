import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.utils.paths import DB_PATH, TICKERS_PATH, MODELS_DIR, BACKTEST_JSON


@st.cache_data
def get_market_data(ticker: str | None = None, limit: int | None = None) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT * FROM market_data"
        params: list = []
        if ticker:
            query += " WHERE ticker = ?"
            params.append(ticker)
        query += " ORDER BY date DESC"
        if limit:
            query += f" LIMIT {limit}"
        return pd.read_sql_query(query, conn, params=params if params else None)


@st.cache_data
def get_signals(status: str | None = None) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT * FROM signals"
        params: list = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY generated_at DESC"
        return pd.read_sql_query(query, conn, params=params if params else None)


@st.cache_data
def get_outcomes() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        query = """
            SELECT
                o.id, o.signal_id, o.resolved_at, o.outcome, o.pct_return, o.exit_price,
                s.ticker, s.generated_at, s.signal_type, s.entry_price, s.target_price,
                s.stop_loss, s.confidence, s.model_version, s.status, s.expected_hold_time
            FROM outcomes o
            JOIN signals s ON o.signal_id = s.id
            ORDER BY o.resolved_at DESC
        """
        return pd.read_sql_query(query, conn)


@st.cache_data
def get_ticker_coverage() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        query = """
            SELECT
                ticker,
                COUNT(*) AS row_count,
                MIN(date) AS min_date,
                MAX(date) AS max_date
            FROM market_data
            GROUP BY ticker
            ORDER BY ticker
        """
        return pd.read_sql_query(query, conn)


@st.cache_data
def get_tickers() -> list[str]:
    if not TICKERS_PATH.exists():
        return []
    with open(TICKERS_PATH) as f:
        data = json.load(f)
    if isinstance(data, list):
        return sorted(data)
    if isinstance(data, dict):
        return sorted(data.get("tickers", data.get("symbols", list(data.keys()))))
    return []


@st.cache_data
def get_model_versions() -> list[dict]:
    versions = []
    for json_path in sorted(MODELS_DIR.glob("model_v*.json")):
        with open(json_path) as f:
            meta = json.load(f)
        versions.append(meta)
    return versions


@st.cache_data
def get_backtest_summary() -> dict:
    if not BACKTEST_JSON.exists():
        return {}
    with open(BACKTEST_JSON) as f:
        return json.load(f)
