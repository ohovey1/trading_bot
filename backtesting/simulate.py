"""
Simulates historical trade signals by replaying the model over past OHLCV data.

Useful for bootstrapping performance metrics before real signals accumulate.
Simulated signals are NOT persisted to the live signals table.
"""
import json
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from pandas.tseries.offsets import BDay

from data.schema import market_data, metadata
from modeling.features import build_features, FEATURE_COLS
from models import registry

CONFIDENCE_THRESHOLD = 0.55
EXPECTED_HOLD_DAYS = 10
_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = _ROOT / "models"
DB_PATH = str(_ROOT / "data" / "trading.db")


def _load_model_with_version():
    jsons = sorted(MODELS_DIR.glob("model_v*.json"))
    if not jsons:
        raise FileNotFoundError(f"No model metadata found in {MODELS_DIR}/")
    with open(jsons[-1]) as f:
        meta = json.load(f)
    pipeline = registry.load_model()
    return pipeline, meta["version"]


def simulate_historical_signals(db_path: str = DB_PATH) -> list[dict]:
    """Replay the model on historical OHLCV data and resolve each simulated signal.

    For each ticker, generates signals at every date where confidence >= 0.55,
    then resolves them using the actual close price EXPECTED_HOLD_DAYS trading
    days later.

    Returns a list of resolved signal dicts. Does NOT write to the database.
    """
    pipeline, version = _load_model_with_version()

    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    with engine.connect() as conn:
        df = pd.read_sql(sa.select(market_data), conn, parse_dates=["date"])

    if df.empty:
        return []

    # Build features across all tickers at once (drops last 10 rows per ticker)
    features_df = build_features(df)
    if features_df.empty:
        return []

    # Build per-ticker price lookup for resolving exit prices
    ticker_prices: dict[str, pd.Series] = {}
    for ticker, grp in df.groupby("ticker"):
        ticker_prices[ticker] = grp.set_index("date")["close"].sort_index()

    results = []
    for _, row in features_df.iterrows():
        X = row[FEATURE_COLS].to_frame().T
        proba = float(pipeline.predict_proba(X)[0][1])

        if proba < CONFIDENCE_THRESHOLD:
            continue

        ticker = row["ticker"]
        signal_date = row["date"]
        entry_price = float(row["close"])

        resolution_ts = pd.Timestamp(signal_date) + BDay(EXPECTED_HOLD_DAYS)

        prices = ticker_prices.get(ticker)
        if prices is None:
            continue

        exit_price = prices.asof(resolution_ts)
        if pd.isna(exit_price):
            continue

        exit_price = float(exit_price)
        pct_return = (exit_price - entry_price) / entry_price

        if pct_return >= 0.03:
            outcome = "win"
        elif pct_return <= -0.03:
            outcome = "loss"
        else:
            outcome = "neutral"

        results.append({
            "ticker": ticker,
            "signal_date": signal_date.date() if hasattr(signal_date, "date") else signal_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pct_return": pct_return,
            "outcome": outcome,
            "confidence": proba,
            "model_version": version,
            "expected_hold_time": EXPECTED_HOLD_DAYS,
        })

    return results


if __name__ == "__main__":
    signals = simulate_historical_signals()
    wins = sum(1 for s in signals if s["outcome"] == "win")
    losses = sum(1 for s in signals if s["outcome"] == "loss")
    print(f"Simulated {len(signals)} historical signals: {wins} wins, {losses} losses")
    if signals:
        returns = [s["pct_return"] for s in signals]
        avg = sum(returns) / len(returns)
        print(f"Avg pct_return: {avg:.2%}")
