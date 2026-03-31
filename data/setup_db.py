"""
Initialize the SQLite database at data/trading.db.

Usage:
    python -m data.setup_db
"""
import pathlib
import sqlalchemy as sa
from data.schema import metadata

DB_PATH = pathlib.Path(__file__).parent / "trading.db"
DB_URL = f"sqlite:///{DB_PATH}"


def init_db(url: str = DB_URL) -> sa.Engine:
    engine = sa.create_engine(url)
    metadata.create_all(engine)
    return engine


if __name__ == "__main__":
    engine = init_db()
    print(f"Database initialized at {DB_PATH}")
