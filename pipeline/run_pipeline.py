"""
Manual end-to-end runner. Executes all four pipeline stages once in sequence
by calling domain functions directly — no Prefect server required.
Use this for local testing or a one-shot full run.

Usage:
    uv run python -m pipeline.run_pipeline
"""
import os
import sys
from pathlib import Path

from backtesting.resolve import resolve_outcomes
from backtesting.run_backtest import main as backtest_main
from data.run_universe_ingest import main as ingest_main
from signals.run_signals import main as signals_main

_STAGES = [
    ("1/4  daily_ingest         ", ingest_main),
    ("2/4  market_open_signals  ", signals_main),
    ("3/4  intraday_reeval      ", lambda db_path: print(f"    resolved={resolve_outcomes(db_path=db_path)} signal(s)") or None),
    ("4/4  market_close_outcomes", backtest_main),
]


def main() -> None:
    db_path = os.environ.get("TRADING_DB_PATH") or str(
        Path(__file__).resolve().parent.parent / "data" / "trading.db"
    )
    print(f"Pipeline start — db={db_path}\n{'=' * 60}")

    for label, fn in _STAGES:
        print(f"\n>>> {label}")
        try:
            fn(db_path=db_path)
            print(f"    {label.strip()} — OK")
        except Exception as exc:
            print(f"    {label.strip()} — FAILED: {exc}", file=sys.stderr)
            raise

    print(f"\n{'=' * 60}\nPipeline complete.")


if __name__ == "__main__":
    main()
