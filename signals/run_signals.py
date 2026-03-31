"""
Entrypoint for signal generation.

Runs the migration, generates signals, persists them, and prints a summary.
"""
from data.migrate import add_missing_columns
from signals.generate import DB_PATH as _DEFAULT_DB, generate_signals, persist_signals


def main(db_path: str | None = None):
    db = db_path if db_path is not None else _DEFAULT_DB
    add_missing_columns(db_path=db)

    signals = generate_signals(db_path=db)
    persist_signals(signals, db_path=db)

    tickers = [s["ticker"] for s in signals]
    print(f"Signals generated: {len(signals)}")
    if tickers:
        print(f"Tickers: {', '.join(tickers)}")
    else:
        print("No tickers met the confidence threshold.")


if __name__ == "__main__":
    main()
