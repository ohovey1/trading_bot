"""
Entrypoint for signal generation.

Runs the migration, generates signals, persists them, and prints a summary.
"""
from data.migrate import add_missing_columns
from signals.generate import generate_signals, persist_signals


def main():
    add_missing_columns()

    signals = generate_signals()
    persist_signals(signals)

    tickers = [s["ticker"] for s in signals]
    print(f"Signals generated: {len(signals)}")
    if tickers:
        print(f"Tickers: {', '.join(tickers)}")
    else:
        print("No tickers met the confidence threshold.")


if __name__ == "__main__":
    main()
