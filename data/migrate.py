"""
Database migrations for the trading signal system.
Run directly or import add_missing_columns() to apply schema changes safely.
"""
import sqlalchemy as sa

DB_PATH = "data/trading.db"


def add_missing_columns(db_path: str = DB_PATH) -> None:
    """Add expected_hold_time and notes to the signals table if they don't exist.

    Safe to run multiple times — skips columns that already exist.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        result = conn.execute(sa.text("PRAGMA table_info(signals)"))
        existing = {row[1] for row in result}

        if "expected_hold_time" not in existing:
            conn.execute(sa.text("ALTER TABLE signals ADD COLUMN expected_hold_time INTEGER"))
        if "notes" not in existing:
            conn.execute(sa.text("ALTER TABLE signals ADD COLUMN notes TEXT"))

        conn.commit()

    # outcomes table migrations
    with engine.connect() as conn:
        result = conn.execute(sa.text("PRAGMA table_info(outcomes)"))
        existing = {row[1] for row in result}

        if "exit_price" not in existing:
            # outcomes may not exist yet in older DBs — only migrate if it does
            result = conn.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='outcomes'")
            )
            if result.fetchone():
                conn.execute(sa.text("ALTER TABLE outcomes ADD COLUMN exit_price REAL"))
                conn.commit()


if __name__ == "__main__":
    add_missing_columns()
    print("Migration complete.")
