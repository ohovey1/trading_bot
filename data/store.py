"""
Persists normalized OHLCV data into the SQLite market_data table.
"""
import datetime
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

from data.schema import market_data, metadata

_DEFAULT_DB = str(Path(__file__).resolve().parent / "trading.db")


def store_market_data(df: pd.DataFrame, db_path: str = _DEFAULT_DB) -> int:
    """Upsert rows into market_data, skipping duplicates on (ticker, date).

    Returns the count of newly inserted rows.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    with engine.connect() as conn:
        existing = set(
            conn.execute(sa.select(market_data.c.ticker, market_data.c.date)).fetchall()
        )

        now = datetime.datetime.utcnow()
        rows = []
        for row in df.itertuples(index=False):
            if (row.ticker, row.date) in existing:
                continue
            rows.append(
                {
                    "ticker": row.ticker,
                    "date": row.date,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": int(row.volume),
                    "ingested_at": now,
                }
            )

        if rows:
            conn.execute(market_data.insert(), rows)
            conn.commit()

    return len(rows)
