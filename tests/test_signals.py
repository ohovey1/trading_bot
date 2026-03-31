"""
Tests for the signal generation layer.
"""
import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from data.migrate import add_missing_columns
from data.schema import market_data, metadata
from signals.generate import generate_signals, persist_signals


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv_rows(tickers: list[str], n: int = 50) -> list[dict]:
    rows = []
    base = datetime.date(2024, 1, 1)
    for ticker in tickers:
        for i in range(n):
            date = base + datetime.timedelta(days=i)
            price = 10.0 + i * 0.02
            rows.append({
                "ticker": ticker,
                "date": date,
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 200_000,
                "ingested_at": datetime.datetime.utcnow(),
            })
    return rows


@pytest.fixture()
def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    rows = _make_ohlcv_rows(["AAA", "BBB"])
    with engine.connect() as conn:
        conn.execute(market_data.insert(), rows)
        conn.commit()
    return db_path


def _mock_model(proba: float = 0.65):
    """Return a mock sklearn-style pipeline with fixed predict_proba output."""
    from unittest.mock import MagicMock
    model = MagicMock()
    model.predict_proba.return_value = np.array([[1 - proba, proba]])
    return model


# ---------------------------------------------------------------------------
# generate_signals tests
# ---------------------------------------------------------------------------

def test_generate_signals_returns_list(temp_db):
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(), "v1")):
        result = generate_signals(db_path=temp_db)
    assert isinstance(result, list)


def test_generate_signals_required_keys(temp_db):
    required = {
        "ticker", "entry", "target", "stop_loss", "confidence",
        "expected_hold_time", "model_version", "signal_date",
    }
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(), "v1")):
        result = generate_signals(db_path=temp_db)
    assert len(result) > 0
    for s in result:
        assert required.issubset(s.keys()), f"Missing keys: {required - s.keys()}"


def test_generate_signals_confidence_at_or_above_threshold(temp_db):
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(0.65), "v1")):
        result = generate_signals(db_path=temp_db)
    for s in result:
        assert s["confidence"] >= 0.55


def test_generate_signals_below_threshold_excluded(temp_db):
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(0.40), "v1")):
        result = generate_signals(db_path=temp_db)
    assert result == []


def test_generate_signals_target_price(temp_db):
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(), "v1")):
        result = generate_signals(db_path=temp_db)
    assert len(result) > 0
    for s in result:
        assert s["target"] == round(s["entry"] * 1.05, 2)


def test_generate_signals_stop_loss(temp_db):
    with patch("signals.generate._load_model_with_version", return_value=(_mock_model(), "v1")):
        result = generate_signals(db_path=temp_db)
    assert len(result) > 0
    for s in result:
        assert s["stop_loss"] == round(s["entry"] * 0.97, 2)


# ---------------------------------------------------------------------------
# add_missing_columns idempotency
# ---------------------------------------------------------------------------

def test_add_missing_columns_idempotent(tmp_path):
    db_path = str(tmp_path / "migrate_test.db")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    # First call: columns may or may not be present depending on schema state
    add_missing_columns(db_path=db_path)
    # Second call: must not raise
    add_missing_columns(db_path=db_path)

    # Verify columns are present
    with engine.connect() as conn:
        result = conn.execute(sa.text("PRAGMA table_info(signals)"))
        cols = {row[1] for row in result}
    assert "expected_hold_time" in cols
    assert "notes" in cols
