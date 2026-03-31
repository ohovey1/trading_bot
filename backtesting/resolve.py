"""
Resolves open signals by checking if their hold period has elapsed
and computing actual returns from market data.
"""
import datetime

import pandas as pd
import sqlalchemy as sa
from pandas.tseries.offsets import BDay

from data.schema import market_data, signals as signals_table, outcomes as outcomes_table, metadata

DB_PATH = "data/trading.db"
EXPECTED_HOLD_DAYS_DEFAULT = 10


def resolve_outcomes(db_path: str = DB_PATH) -> int:
    """Resolve open signals where the hold period has elapsed.

    For each open signal, checks if expected_hold_time trading days have passed
    since the signal was generated. If so, fetches the close price at the
    resolution date from OHLCV data, computes pct_return, classifies the
    outcome, and writes a record to the outcomes table.

    Returns the count of signals resolved.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    today = datetime.date.today()

    with engine.connect() as conn:
        open_signals = conn.execute(
            sa.select(signals_table).where(signals_table.c.status == "open")
        ).fetchall()

        if not open_signals:
            return 0

        df = pd.read_sql(sa.select(market_data), conn, parse_dates=["date"])

    if df.empty:
        return 0

    # Build per-ticker price series for asof lookups (finds price at or before a date)
    ticker_prices: dict[str, pd.Series] = {}
    for ticker, grp in df.groupby("ticker"):
        ticker_prices[ticker] = grp.set_index("date")["close"].sort_index()

    resolved = 0
    with engine.connect() as conn:
        for row in open_signals:
            sig = row._mapping
            ticker = sig["ticker"]
            hold_days = sig["expected_hold_time"] or EXPECTED_HOLD_DAYS_DEFAULT

            generated_at = sig["generated_at"]
            if isinstance(generated_at, str):
                generated_at = datetime.datetime.fromisoformat(generated_at)
            signal_date = generated_at.date() if hasattr(generated_at, "date") else generated_at

            resolution_ts = pd.Timestamp(signal_date) + BDay(hold_days)
            if resolution_ts.date() > today:
                continue

            prices = ticker_prices.get(ticker)
            if prices is None:
                continue

            exit_price = prices.asof(resolution_ts)
            if pd.isna(exit_price):
                continue

            exit_price = float(exit_price)
            entry_price = float(sig["entry_price"])
            pct_return = (exit_price - entry_price) / entry_price

            if pct_return >= 0.03:
                outcome = "win"
            elif pct_return <= -0.03:
                outcome = "loss"
            else:
                outcome = "neutral"

            conn.execute(
                outcomes_table.insert().values(
                    signal_id=sig["id"],
                    resolved_at=datetime.datetime.utcnow(),
                    outcome=outcome,
                    pct_return=pct_return,
                    exit_price=exit_price,
                )
            )
            conn.execute(
                signals_table.update()
                .where(signals_table.c.id == sig["id"])
                .values(status="closed")
            )
            resolved += 1

        conn.commit()

    return resolved
