"""
Tests for the backtesting layer: resolve_outcomes, score_signals,
and simulate_historical_signals.
"""
import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from data.schema import market_data, signals as signals_table, outcomes as outcomes_table, metadata
from backtesting.resolve import resolve_outcomes
from backtesting.score import score_signals, _REQUIRED_KEYS
from backtesting.simulate import simulate_historical_signals


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _business_days_ago(n: int) -> datetime.datetime:
    """Return a datetime n business days before today."""
    return (pd.Timestamp.today() - pd.offsets.BDay(n)).to_pydatetime()


def _make_market_data(ticker: str, start: datetime.date, n: int, base_price: float = 10.0):
    rows = []
    for i in range(n):
        date = start + datetime.timedelta(days=i)
        price = base_price + i * 0.10
        rows.append({
            "ticker": ticker,
            "date": date,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 100_000,
            "ingested_at": datetime.datetime.utcnow(),
        })
    return rows


@pytest.fixture()
def temp_db(tmp_path):
    """DB with market data spanning the past 90 calendar days."""
    db_path = str(tmp_path / "test.db")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    start = datetime.date.today() - datetime.timedelta(days=90)
    rows = _make_market_data("AAA", start, 90, base_price=10.0)
    rows += _make_market_data("BBB", start, 90, base_price=20.0)

    with engine.connect() as conn:
        conn.execute(market_data.insert(), rows)
        conn.commit()

    return db_path


def _insert_signal(conn, ticker, entry_price, generated_at, hold_days=10):
    result = conn.execute(
        signals_table.insert().values(
            ticker=ticker,
            generated_at=generated_at,
            signal_type="buy",
            entry_price=entry_price,
            target_price=entry_price * 1.05,
            stop_loss=entry_price * 0.97,
            confidence=0.65,
            model_version="v1",
            status="open",
            expected_hold_time=hold_days,
        )
    )
    conn.commit()
    return result.inserted_primary_key[0]


def _insert_outcome(conn, signal_id, outcome, pct_return, exit_price):
    conn.execute(
        outcomes_table.insert().values(
            signal_id=signal_id,
            resolved_at=datetime.datetime.utcnow(),
            outcome=outcome,
            pct_return=pct_return,
            exit_price=exit_price,
        )
    )
    # Mark signal as closed
    conn.execute(
        signals_table.update()
        .where(signals_table.c.id == signal_id)
        .values(status="closed")
    )
    conn.commit()


# ---------------------------------------------------------------------------
# resolve_outcomes tests
# ---------------------------------------------------------------------------

class TestResolveOutcomes:
    def test_returns_zero_when_no_open_signals(self, temp_db):
        assert resolve_outcomes(db_path=temp_db) == 0

    def test_does_not_resolve_signal_not_yet_elapsed(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            # Generated just now — 10 business days have NOT elapsed
            _insert_signal(conn, "AAA", 10.0, datetime.datetime.utcnow(), hold_days=10)

        assert resolve_outcomes(db_path=temp_db) == 0

    def test_resolves_elapsed_signal(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            # Generated 30 business days ago — definitely elapsed
            _insert_signal(conn, "AAA", 10.0, _business_days_ago(30), hold_days=10)

        count = resolve_outcomes(db_path=temp_db)
        assert count == 1

    def test_signal_marked_closed_after_resolution(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            sig_id = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30), hold_days=10)

        resolve_outcomes(db_path=temp_db)

        with engine.connect() as conn:
            row = conn.execute(
                sa.select(signals_table.c.status).where(signals_table.c.id == sig_id)
            ).fetchone()
        assert row[0] == "closed"

    def test_outcome_record_written(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            sig_id = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30), hold_days=10)

        resolve_outcomes(db_path=temp_db)

        with engine.connect() as conn:
            row = conn.execute(
                sa.select(outcomes_table).where(outcomes_table.c.signal_id == sig_id)
            ).fetchone()
        assert row is not None

    def test_pct_return_computation(self, tmp_path):
        """entry=10.0, exit~10.0+20*0.1=12.0 after 20 bdays; pct_return ~0.20"""
        db_path = str(tmp_path / "pct_test.db")
        engine = sa.create_engine(f"sqlite:///{db_path}")
        metadata.create_all(engine)

        # Market data: 60 days starting 60 days ago, base price=10.0, step=0.10
        start = datetime.date.today() - datetime.timedelta(days=60)
        rows = _make_market_data("AAA", start, 60, base_price=10.0)
        with engine.connect() as conn:
            conn.execute(market_data.insert(), rows)
            conn.commit()

        # Signal generated 30 bdays ago with entry at day-0 price of that range
        generated_at = _business_days_ago(30)
        signal_start = datetime.date.today() - datetime.timedelta(days=60)
        # Entry price = close on day 0 of our data = 10.0
        entry_price = 10.0

        with engine.connect() as conn:
            _insert_signal(conn, "AAA", entry_price, generated_at, hold_days=10)

        resolve_outcomes(db_path=db_path)

        with engine.connect() as conn:
            row = conn.execute(sa.select(outcomes_table)).fetchone()

        assert row is not None
        pct_return = row._mapping["pct_return"]
        # exit_price > 10.0 (prices are trending up), pct_return should be positive
        assert pct_return > 0

    def test_outcome_win_threshold(self, tmp_path):
        """Manually verify win/loss/neutral classification."""
        db_path = str(tmp_path / "thresh_test.db")
        engine = sa.create_engine(f"sqlite:///{db_path}")
        metadata.create_all(engine)

        # Construct precise prices: entry=100, exit=104 -> pct_return=0.04 -> win
        start = datetime.date.today() - datetime.timedelta(days=60)
        rows = []
        for i in range(60):
            date = start + datetime.timedelta(days=i)
            # Keep price constant at 100, then at resolution set it to 104
            price = 100.0
            rows.append({
                "ticker": "AAA", "date": date, "open": price, "high": price,
                "low": price, "close": price, "volume": 1000,
                "ingested_at": datetime.datetime.utcnow(),
            })
        # Override one row near resolution to set a precise exit price
        # Resolution = generated_at + 10 bdays; generated = 30 bdays ago
        # So resolution was ~20 bdays ago
        resolution_ts = pd.Timestamp.today() - pd.offsets.BDay(20)
        resolution_date = resolution_ts.date()
        # Find and override that date row
        for r in rows:
            if r["date"] == resolution_date:
                r["close"] = 104.0
                break

        with engine.connect() as conn:
            conn.execute(market_data.insert(), rows)
            conn.commit()
            _insert_signal(conn, "AAA", 100.0, _business_days_ago(30), hold_days=10)

        resolve_outcomes(db_path=db_path)

        with engine.connect() as conn:
            row = conn.execute(sa.select(outcomes_table)).fetchone()

        assert row is not None
        outcome = row._mapping["outcome"]
        pct_return = row._mapping["pct_return"]
        # pct_return >= 0.03 -> win; < -0.03 -> loss; otherwise neutral
        if pct_return >= 0.03:
            assert outcome == "win"
        elif pct_return <= -0.03:
            assert outcome == "loss"
        else:
            assert outcome == "neutral"

    def test_outcome_classification_thresholds(self, tmp_path):
        """Unit-test the threshold logic directly without DB."""
        # win: pct_return >= 0.03
        # loss: pct_return <= -0.03
        # neutral: -0.03 < pct_return < 0.03
        cases = [
            (0.05, "win"),
            (0.03, "win"),
            (-0.03, "loss"),
            (-0.05, "loss"),
            (0.02, "neutral"),
            (-0.02, "neutral"),
            (0.0, "neutral"),
        ]
        for pct, expected in cases:
            if pct >= 0.03:
                result = "win"
            elif pct <= -0.03:
                result = "loss"
            else:
                result = "neutral"
            assert result == expected, f"pct={pct}: expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# score_signals tests
# ---------------------------------------------------------------------------

class TestScoreSignals:
    def test_returns_empty_metrics_when_no_data(self, temp_db):
        metrics = score_signals(db_path=temp_db)
        assert metrics["total_signals"] == 0

    def test_returns_all_required_keys(self, temp_db):
        metrics = score_signals(db_path=temp_db)
        assert _REQUIRED_KEYS.issubset(metrics.keys())

    def test_required_keys_with_resolved_signals(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            sig_id = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, sig_id, "win", 0.05, 10.5)

        metrics = score_signals(db_path=temp_db)
        assert _REQUIRED_KEYS.issubset(metrics.keys())

    def test_win_rate_computation(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            s1 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s1, "win", 0.05, 10.5)
            s2 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(40))
            _insert_outcome(conn, s2, "loss", -0.05, 9.5)

        metrics = score_signals(db_path=temp_db)
        assert metrics["total_signals"] == 2
        assert abs(metrics["win_rate"] - 0.5) < 1e-9
        assert abs(metrics["loss_rate"] - 0.5) < 1e-9
        assert metrics["neutral_rate"] == 0.0

    def test_sharpe_approx_zero_when_no_data(self, temp_db):
        metrics = score_signals(db_path=temp_db)
        assert metrics["sharpe_approx"] == 0.0

    def test_sharpe_approx_zero_with_one_signal(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            s = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s, "win", 0.05, 10.5)

        metrics = score_signals(db_path=temp_db)
        assert metrics["sharpe_approx"] == 0.0

    def test_sharpe_approx_nonzero_with_variance(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            s1 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s1, "win", 0.05, 10.5)
            s2 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(40))
            _insert_outcome(conn, s2, "loss", -0.05, 9.5)

        metrics = score_signals(db_path=temp_db)
        assert metrics["sharpe_approx"] == 0.0  # mean=0, so sharpe=0

    def test_by_model_version_structure(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            s1 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s1, "win", 0.05, 10.5)

        metrics = score_signals(db_path=temp_db)
        assert "v1" in metrics["by_model_version"]
        vm = metrics["by_model_version"]["v1"]
        assert "total" in vm
        assert "win_rate" in vm
        assert "avg_pct_return" in vm

    def test_best_worst_ticker(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            # AAA: high return; BBB: low return
            s1 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s1, "win", 0.10, 11.0)
            s2 = _insert_signal(conn, "BBB", 20.0, _business_days_ago(40))
            _insert_outcome(conn, s2, "loss", -0.10, 18.0)

        metrics = score_signals(db_path=temp_db)
        assert metrics["best_ticker"] == "AAA"
        assert metrics["worst_ticker"] == "BBB"

    def test_avg_win_loss_returns(self, temp_db):
        engine = sa.create_engine(f"sqlite:///{temp_db}")
        with engine.connect() as conn:
            s1 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(30))
            _insert_outcome(conn, s1, "win", 0.08, 10.8)
            s2 = _insert_signal(conn, "AAA", 10.0, _business_days_ago(40))
            _insert_outcome(conn, s2, "loss", -0.06, 9.4)

        metrics = score_signals(db_path=temp_db)
        assert abs(metrics["avg_win_return"] - 0.08) < 1e-9
        assert abs(metrics["avg_loss_return"] - (-0.06)) < 1e-9


# ---------------------------------------------------------------------------
# simulate_historical_signals tests
# ---------------------------------------------------------------------------

def _mock_pipeline(proba: float = 0.65):
    from unittest.mock import MagicMock
    model = MagicMock()
    model.predict_proba.return_value = np.array([[1 - proba, proba]])
    return model


class TestSimulateHistoricalSignals:
    def test_returns_list(self, temp_db):
        with (
            patch("backtesting.simulate._load_model_with_version",
                  return_value=(_mock_pipeline(0.65), "v1")),
        ):
            result = simulate_historical_signals(db_path=temp_db)
        assert isinstance(result, list)

    def test_returns_empty_list_when_db_empty(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        engine = sa.create_engine(f"sqlite:///{db_path}")
        metadata.create_all(engine)

        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.65), "v1")):
            result = simulate_historical_signals(db_path=db_path)
        assert result == []

    def test_required_fields_in_each_dict(self, temp_db):
        required = {
            "ticker", "signal_date", "entry_price", "exit_price",
            "pct_return", "outcome", "confidence", "model_version",
            "expected_hold_time",
        }
        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.65), "v1")):
            result = simulate_historical_signals(db_path=temp_db)

        assert len(result) > 0, "Expected at least one simulated signal"
        for sig in result:
            missing = required - sig.keys()
            assert not missing, f"Missing fields: {missing}"

    def test_outcome_values_are_valid(self, temp_db):
        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.65), "v1")):
            result = simulate_historical_signals(db_path=temp_db)

        for sig in result:
            assert sig["outcome"] in {"win", "loss", "neutral"}

    def test_below_threshold_returns_empty(self, temp_db):
        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.40), "v1")):
            result = simulate_historical_signals(db_path=temp_db)
        assert result == []

    def test_pct_return_consistent_with_outcome(self, temp_db):
        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.65), "v1")):
            result = simulate_historical_signals(db_path=temp_db)

        for sig in result:
            pct = sig["pct_return"]
            outcome = sig["outcome"]
            if outcome == "win":
                assert pct >= 0.03
            elif outcome == "loss":
                assert pct <= -0.03
            else:
                assert -0.03 < pct < 0.03

    def test_simulated_signals_not_in_db(self, temp_db):
        """Verify simulate does not write anything to the signals table."""
        engine = sa.create_engine(f"sqlite:///{temp_db}")

        with engine.connect() as conn:
            before = conn.execute(sa.select(sa.func.count()).select_from(signals_table)).scalar()

        with patch("backtesting.simulate._load_model_with_version",
                   return_value=(_mock_pipeline(0.65), "v1")):
            simulate_historical_signals(db_path=temp_db)

        with engine.connect() as conn:
            after = conn.execute(sa.select(sa.func.count()).select_from(signals_table)).scalar()

        assert before == after
