"""
Entrypoint for the backtesting pipeline.

Resolves open signals, scores all closed signals, and writes
a summary to backtesting/latest_backtest.json.
"""
import json
from pathlib import Path

from backtesting.resolve import resolve_outcomes
from backtesting.score import score_signals

_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = Path(__file__).resolve().parent / "latest_backtest.json"
_DEFAULT_DB = str(_ROOT / "data" / "trading.db")


def main(db_path: str = _DEFAULT_DB) -> None:
    resolved = resolve_outcomes(db_path=db_path)
    print(f"Resolved {resolved} signal(s).")

    metrics = score_signals(db_path=db_path)

    print("\n--- Backtest Summary ---")
    print(f"Total signals scored : {metrics['total_signals']}")
    print(f"Win rate             : {metrics['win_rate']:.1%}")
    print(f"Loss rate            : {metrics['loss_rate']:.1%}")
    print(f"Neutral rate         : {metrics['neutral_rate']:.1%}")
    print(f"Avg return           : {metrics['avg_pct_return']:.2%}")
    print(f"Avg win return       : {metrics['avg_win_return']:.2%}")
    print(f"Avg loss return      : {metrics['avg_loss_return']:.2%}")
    print(f"Sharpe (approx)      : {metrics['sharpe_approx']:.3f}")
    if metrics["best_ticker"]:
        print(f"Best ticker          : {metrics['best_ticker']}")
        print(f"Worst ticker         : {metrics['worst_ticker']}")
    if metrics["by_model_version"]:
        print("\nBy model version:")
        for version, vm in metrics["by_model_version"].items():
            print(
                f"  {version}: total={vm['total']}, "
                f"win_rate={vm['win_rate']:.1%}, "
                f"avg_return={vm['avg_pct_return']:.2%}"
            )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
