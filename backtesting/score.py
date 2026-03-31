"""
Retrospective scoring of closed signals and historical model validation.
"""
import pandas as pd
import sqlalchemy as sa

from data.schema import signals as signals_table, outcomes as outcomes_table, metadata

DB_PATH = "data/trading.db"

_REQUIRED_KEYS = {
    "total_signals",
    "win_rate",
    "loss_rate",
    "neutral_rate",
    "avg_pct_return",
    "avg_win_return",
    "avg_loss_return",
    "sharpe_approx",
    "best_ticker",
    "worst_ticker",
    "by_model_version",
}

_EMPTY_METRICS: dict = {
    "total_signals": 0,
    "win_rate": 0.0,
    "loss_rate": 0.0,
    "neutral_rate": 0.0,
    "avg_pct_return": 0.0,
    "avg_win_return": 0.0,
    "avg_loss_return": 0.0,
    "sharpe_approx": 0.0,
    "best_ticker": "",
    "worst_ticker": "",
    "by_model_version": {},
}


def score_signals(db_path: str = DB_PATH) -> dict:
    """Score all resolved signals and return a metrics dict.

    Returns a dict with keys: total_signals, win_rate, loss_rate, neutral_rate,
    avg_pct_return, avg_win_return, avg_loss_return, sharpe_approx,
    best_ticker, worst_ticker, by_model_version.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    with engine.connect() as conn:
        query = (
            sa.select(
                signals_table.c.ticker,
                signals_table.c.model_version,
                outcomes_table.c.outcome,
                outcomes_table.c.pct_return,
            ).join(outcomes_table, signals_table.c.id == outcomes_table.c.signal_id)
        )
        rows = conn.execute(query).fetchall()

    if not rows:
        return dict(_EMPTY_METRICS)

    df = pd.DataFrame(rows, columns=["ticker", "model_version", "outcome", "pct_return"])
    total = len(df)

    win_mask = df["outcome"] == "win"
    loss_mask = df["outcome"] == "loss"
    neutral_mask = df["outcome"] == "neutral"

    win_rate = win_mask.sum() / total
    loss_rate = loss_mask.sum() / total
    neutral_rate = neutral_mask.sum() / total
    avg_pct_return = float(df["pct_return"].mean())

    wins = df.loc[win_mask, "pct_return"]
    losses = df.loc[loss_mask, "pct_return"]
    avg_win_return = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss_return = float(losses.mean()) if len(losses) > 0 else 0.0

    std = df["pct_return"].std()
    sharpe_approx = float(avg_pct_return / std) if (len(df) >= 2 and std > 0) else 0.0

    ticker_avg = df.groupby("ticker")["pct_return"].mean()
    best_ticker = str(ticker_avg.idxmax()) if not ticker_avg.empty else ""
    worst_ticker = str(ticker_avg.idxmin()) if not ticker_avg.empty else ""

    by_model_version: dict[str, dict] = {}
    for version, grp in df.groupby("model_version"):
        n = len(grp)
        v_wins = (grp["outcome"] == "win").sum()
        by_model_version[str(version)] = {
            "total": n,
            "win_rate": v_wins / n,
            "avg_pct_return": float(grp["pct_return"].mean()),
        }

    return {
        "total_signals": total,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "neutral_rate": neutral_rate,
        "avg_pct_return": avg_pct_return,
        "avg_win_return": avg_win_return,
        "avg_loss_return": avg_loss_return,
        "sharpe_approx": sharpe_approx,
        "best_ticker": best_ticker,
        "worst_ticker": worst_ticker,
        "by_model_version": by_model_version,
    }
