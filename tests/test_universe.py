"""Tests for the ticker universe and data quality audit."""

import re
from unittest.mock import patch

import pytest

from data.universe import load_universe


def test_load_universe_returns_nonempty_list():
    tickers = load_universe()
    assert isinstance(tickers, list)
    assert len(tickers) > 0


def test_all_entries_are_uppercase_ticker_strings():
    tickers = load_universe()
    for t in tickers:
        assert isinstance(t, str), f"{t!r} is not a string"
        assert t == t.upper(), f"{t!r} is not uppercase"
        assert " " not in t, f"{t!r} contains a space"
        assert re.match(r"^[A-Z]+$", t), f"{t!r} contains non-alpha characters"


def test_audit_universe_returns_dict_with_expected_keys():
    from data.audit import audit_universe

    mock_rows = {
        "AEIS": [("2023-01-03",)] * 250,
        "ARLO": [("2023-01-03",)] * 250,
    }

    def fake_execute(query, params=None):
        ticker = (params or {}).get("t", "")

        class FakeResult:
            def fetchall(self_):
                return mock_rows.get(ticker, [])

        return FakeResult()

    class FakeConn:
        def execute(self, query, params=None):
            return fake_execute(query, params)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FakeEngine:
        def connect(self):
            return FakeConn()

    with patch("data.audit.load_universe", return_value=["AEIS", "ARLO"]), \
         patch("data.audit.create_engine", return_value=FakeEngine()):
        result = audit_universe()

    assert isinstance(result, dict)
    assert "AEIS" in result
    for key in ("row_count", "min_date", "max_date", "gap_count", "sufficient"):
        assert key in result["AEIS"], f"Missing key: {key}"


def test_audit_universe_sufficient_tickers():
    """At least 30 tickers must have >=200 rows. Uses real DB if available, else skips."""
    import os
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        pytest.skip("trading.db not present — skipping live DB test")

    from data.audit import audit_universe
    stats = audit_universe(db_path)
    sufficient_count = sum(1 for s in stats.values() if s["sufficient"])
    assert sufficient_count >= 30, (
        f"Only {sufficient_count} tickers have sufficient data (need >=30)"
    )
