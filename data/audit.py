"""
Data quality audit for the ticker universe.

Run with: uv run python -m data.audit
"""

from datetime import timedelta

import pandas as pd
from sqlalchemy import create_engine, text

from data.universe import load_universe


def audit_universe(db_path: str = "data/trading.db") -> dict:
    """
    Query market_data for each ticker in the universe and return quality stats.

    Returns a dict keyed by ticker with:
      - row_count: int
      - min_date: date or None
      - max_date: date or None
      - gap_count: int (spans of 7+ calendar days between consecutive trading dates)
      - sufficient: bool (True if row_count >= 200)
    """
    engine = create_engine(f"sqlite:///{db_path}")
    tickers = load_universe()
    results = {}

    with engine.connect() as conn:
        for ticker in tickers:
            rows = conn.execute(
                text("SELECT date FROM market_data WHERE ticker = :t ORDER BY date"),
                {"t": ticker},
            ).fetchall()

            if not rows:
                results[ticker] = {
                    "row_count": 0,
                    "min_date": None,
                    "max_date": None,
                    "gap_count": 0,
                    "sufficient": False,
                }
                continue

            dates = [r[0] for r in rows]
            # dates may come back as strings from SQLite
            dates = pd.to_datetime(dates).tolist()

            gap_count = sum(
                1
                for a, b in zip(dates, dates[1:])
                if (b - a) >= timedelta(days=7)
            )

            results[ticker] = {
                "row_count": len(dates),
                "min_date": dates[0].date(),
                "max_date": dates[-1].date(),
                "gap_count": gap_count,
                "sufficient": len(dates) >= 200,
            }

    return results


if __name__ == "__main__":
    stats = audit_universe()

    sufficient = [t for t, s in stats.items() if s["sufficient"]]
    insufficient = [t for t, s in stats.items() if not s["sufficient"]]

    print(f"{'Ticker':<8} {'Rows':>6} {'Min Date':>12} {'Max Date':>12} {'Gaps':>5} {'Status':>12}")
    print("-" * 62)
    for ticker, s in sorted(stats.items()):
        status = "OK" if s["sufficient"] else "INSUFFICIENT"
        min_d = str(s["min_date"]) if s["min_date"] else "N/A"
        max_d = str(s["max_date"]) if s["max_date"] else "N/A"
        print(f"{ticker:<8} {s['row_count']:>6} {min_d:>12} {max_d:>12} {s['gap_count']:>5} {status:>12}")

    print()
    print(f"Sufficient (>=200 rows): {len(sufficient)}")
    print(f"Insufficient (<200 rows): {len(insufficient)}")
    if insufficient:
        print(f"  Flagged: {', '.join(sorted(insufficient))}")
