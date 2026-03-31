import sqlalchemy as sa
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from data.schema import market_data, metadata
from data.universe import load_universe
from modeling.features import build_features, FEATURE_COLS


def _load_ticker_data(ticker: str, engine) -> pd.DataFrame:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(market_data).where(market_data.c.ticker == ticker)
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=[c.name for c in market_data.columns])


def train_model(db_path: str = "data/trading.db") -> tuple[Pipeline, dict, dict]:
    """Train a StandardScaler + LogisticRegression pipeline on all universe tickers.

    Returns (pipeline, train_metrics, test_metrics).
    Raises ValueError if test ROC-AUC <= 0.50.
    """
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)

    tickers = load_universe()
    parts = []
    for ticker in tickers:
        df = _load_ticker_data(ticker, engine)
        if df.empty:
            continue
        try:
            feat = build_features(df)
            if len(feat) > 0:
                parts.append(feat)
        except Exception:
            continue

    if not parts:
        raise ValueError("No feature data available. Run ingestion first.")

    full = pd.concat(parts, ignore_index=True).sort_values(["date", "ticker"])

    X = full[FEATURE_COLS]
    y = full["label"]

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=42, max_iter=1000, C=0.1)),
    ])
    pipeline.fit(X_train, y_train)

    def _metrics(X_part, y_part, split_name: str) -> dict:
        preds = pipeline.predict(X_part)
        proba = pipeline.predict_proba(X_part)[:, 1]
        return {
            "split": split_name,
            "n": len(y_part),
            "accuracy": round(accuracy_score(y_part, preds), 4),
            "roc_auc": round(roc_auc_score(y_part, proba), 4),
            "classification_report": classification_report(y_part, preds, zero_division=0),
        }

    train_metrics = _metrics(X_train, y_train, "train")
    test_metrics = _metrics(X_test, y_test, "test")

    if test_metrics["roc_auc"] <= 0.50:
        raise ValueError(
            f"Test ROC-AUC {test_metrics['roc_auc']:.4f} did not exceed 0.50. "
            "Check feature quality or data coverage."
        )

    return pipeline, train_metrics, test_metrics
