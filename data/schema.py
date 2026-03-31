"""
SQLAlchemy Core table definitions for the trading signal system.
"""
import sqlalchemy as sa

metadata = sa.MetaData()

market_data = sa.Table(
    "market_data",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ticker", sa.String, nullable=False),
    sa.Column("date", sa.Date, nullable=False),
    sa.Column("open", sa.Float, nullable=False),
    sa.Column("high", sa.Float, nullable=False),
    sa.Column("low", sa.Float, nullable=False),
    sa.Column("close", sa.Float, nullable=False),
    sa.Column("volume", sa.BigInteger, nullable=False),
    sa.Column("ingested_at", sa.DateTime, nullable=False),
    sa.UniqueConstraint("ticker", "date", name="uq_market_data_ticker_date"),
)

signals = sa.Table(
    "signals",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ticker", sa.String, nullable=False),
    sa.Column("generated_at", sa.DateTime, nullable=False),
    sa.Column("signal_type", sa.String, nullable=False),   # buy / sell / hold
    sa.Column("entry_price", sa.Float, nullable=False),
    sa.Column("target_price", sa.Float, nullable=False),
    sa.Column("stop_loss", sa.Float, nullable=False),
    sa.Column("confidence", sa.Float, nullable=False),     # 0.0 – 1.0
    sa.Column("model_version", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False, server_default="open"),  # open / closed
)

outcomes = sa.Table(
    "outcomes",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id"), nullable=False),
    sa.Column("resolved_at", sa.DateTime, nullable=False),
    sa.Column("outcome", sa.String, nullable=False),       # win / loss / neutral
    sa.Column("pct_return", sa.Float, nullable=False),
)
