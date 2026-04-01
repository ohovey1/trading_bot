"""
Generates trade signals by running the latest model over current OHLCV data.
"""
import datetime
import json
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

from data.schema import market_data, signals as signals_table
from modeling.features import build_features, FEATURE_COLS
from models import registry

CONFIDENCE_THRESHOLD = 0.55
EXPECTED_HOLD_DAYS = 10
_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = _ROOT / "models"
DB_PATH = str(_ROOT / "data" / "trading.db")

# v1 is the production model; v2/v3 exist for comparison only.
PRODUCTION_VERSION = "v1"


def _load_model_with_version():
    """Load the production model pipeline and return (pipeline, version_string)."""
    json_path = MODELS_DIR / f"model_{PRODUCTION_VERSION}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Production model not found: {json_path}")
    with open(json_path) as f:
        meta = json.load(f)
    pipeline = registry.load_model(version=PRODUCTION_VERSION)
    return pipeline, meta["version"]


def generate_signals(db_path: str = DB_PATH) -> list[dict]:
    """Return a list of buy signal dicts for tickers where confidence >= 0.55."""
    pipeline, version = _load_model_with_version()

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        df = pd.read_sql(sa.select(market_data), conn, parse_dates=["date"])

    if df.empty:
        return []

    today = datetime.date.today().isoformat()
    signals = []

    for ticker, group in df.groupby("ticker"):
        features_df = build_features(group)
        if features_df.empty:
            continue

        latest = features_df.iloc[-1]
        X = latest[FEATURE_COLS].to_frame().T
        proba = float(pipeline.predict_proba(X)[0][1])

        if proba >= CONFIDENCE_THRESHOLD:
            entry = round(float(latest["close"]), 2)
            signals.append({
                "ticker": ticker,
                "entry": entry,
                "target": round(entry * 1.05, 2),
                "stop_loss": round(entry * 0.97, 2),
                "confidence": proba,
                "expected_hold_time": EXPECTED_HOLD_DAYS,
                "model_version": version,
                "signal_date": today,
                "notes": None,
            })

    return signals


def persist_signals(signals: list[dict], db_path: str = DB_PATH) -> None:
    """Insert signal dicts into the signals table."""
    if not signals:
        return

    engine = sa.create_engine(f"sqlite:///{db_path}")
    now = datetime.datetime.utcnow()
    rows = [
        {
            "ticker": s["ticker"],
            "generated_at": now,
            "signal_type": "buy",
            "entry_price": s["entry"],
            "target_price": s["target"],
            "stop_loss": s["stop_loss"],
            "confidence": s["confidence"],
            "model_version": s["model_version"],
            "status": "open",
            "expected_hold_time": s["expected_hold_time"],
            "notes": s["notes"],
        }
        for s in signals
    ]

    with engine.connect() as conn:
        conn.execute(signals_table.insert(), rows)
        conn.commit()
