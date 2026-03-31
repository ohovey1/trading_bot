"""
Prefect flows for the trading signal pipeline.

Schedules (all UTC, targeting US Eastern market hours):
  daily_ingest_flow        : 0 14 * * 1-5   (9:00 AM ET)
  market_open_signals_flow : 30 14 * * 1-5  (9:30 AM ET)
  intraday_reeval_flow     : 0 16,18,20 * * 1-5  (11 AM, 1 PM, 3 PM ET)
  market_close_outcomes_flow: 30 21 * * 1-5 (4:30 PM ET)
"""
import os
from pathlib import Path

from prefect import flow, task

from backtesting.resolve import resolve_outcomes
from backtesting.run_backtest import main as backtest_main
from data.run_universe_ingest import main as ingest_main
from signals.run_signals import main as signals_main


def _resolve_db(override: str | None) -> str:
    if override:
        return override
    env = os.environ.get("TRADING_DB_PATH")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "data" / "trading.db")


@task(name="ingest-universe")
def ingest_universe(db_path: str) -> None:
    ingest_main(db_path=db_path)


@task(name="generate-signals")
def generate_signals_task(db_path: str) -> None:
    signals_main(db_path=db_path)


@task(name="resolve-open-signals")
def resolve_open_signals(db_path: str) -> int:
    return resolve_outcomes(db_path=db_path)


@task(name="run-backtest")
def run_backtest(db_path: str) -> None:
    backtest_main(db_path=db_path)


@flow(name="daily-ingest")
def daily_ingest_flow(db_path: str | None = None) -> None:
    """Fetch 2 years of OHLCV data for the full ticker universe."""
    db = _resolve_db(db_path)
    print(f"[daily-ingest] db={db}")
    ingest_universe(db_path=db)
    print("[daily-ingest] done")


@flow(name="market-open-signals")
def market_open_signals_flow(db_path: str | None = None) -> None:
    """Run DB migration and generate trade signals at market open."""
    db = _resolve_db(db_path)
    print(f"[market-open-signals] db={db}")
    generate_signals_task(db_path=db)
    print("[market-open-signals] done")


@flow(name="intraday-reeval")
def intraday_reeval_flow(db_path: str | None = None) -> None:
    """Resolve any open signals whose hold period has elapsed."""
    db = _resolve_db(db_path)
    print(f"[intraday-reeval] db={db}")
    resolved = resolve_open_signals(db_path=db)
    print(f"[intraday-reeval] resolved={resolved} signal(s)")


@flow(name="market-close-outcomes")
def market_close_outcomes_flow(db_path: str | None = None) -> None:
    """Resolve outcomes and score all closed signals at market close."""
    db = _resolve_db(db_path)
    print(f"[market-close-outcomes] db={db}")
    run_backtest(db_path=db)
    print("[market-close-outcomes] done")
