from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "trading.db"
TICKERS_PATH = REPO_ROOT / "data" / "tickers.json"
MODELS_DIR = REPO_ROOT / "models"
BACKTEST_JSON = REPO_ROOT / "backtesting" / "latest_backtest.json"
MODEL_CARD_PATH = REPO_ROOT / "modeling" / "MODEL_CARD.md"
UNIVERSE_SUMMARY_PATH = REPO_ROOT / "data" / "universe_summary.md"
PERF_REPORT_PATH = REPO_ROOT / "docs" / "model_performance_report.md"
PIPELINE_FLOWS_PATH = REPO_ROOT / "pipeline" / "flows.py"
