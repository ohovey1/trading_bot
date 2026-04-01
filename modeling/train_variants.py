"""Train v2 (Momentum+Volume) and v3 (Volatility+Mean-reversion) models."""
import datetime
import json
import pickle
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from data.schema import market_data, metadata
from data.universe import load_universe
from modeling.features import (
    FEATURE_COLS_V2,
    FEATURE_COLS_V3,
    FORWARD_DAYS,
    LABEL_THRESHOLD,
    build_features_v2,
    build_features_v3,
)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def _load_all_data(db_path: str) -> pd.DataFrame:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    tickers = load_universe()
    parts = []
    for ticker in tickers:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.select(market_data).where(market_data.c.ticker == ticker)
            ).fetchall()
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=[c.name for c in market_data.columns])
        if len(df) > 0:
            parts.append(df)
    if not parts:
        raise ValueError("No data in database. Run ingestion first.")
    return pd.concat(parts, ignore_index=True)


def _train_and_save(
    raw_df: pd.DataFrame,
    feature_cols: list[str],
    build_fn,
    pipeline: Pipeline,
    version: str,
    algorithm_name: str,
    hyperparams: dict,
) -> dict:
    full = build_fn(raw_df).sort_values(["date", "ticker"])

    if full.empty:
        raise ValueError(f"No feature data built for {version}")

    X = full[feature_cols]
    y = full["label"]

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    pipeline.fit(X_train, y_train)

    train_metrics = {
        "accuracy": round(accuracy_score(y_train, pipeline.predict(X_train)), 4),
        "roc_auc": round(roc_auc_score(y_train, pipeline.predict_proba(X_train)[:, 1]), 4),
        "n": len(y_train),
    }
    test_metrics = {
        "accuracy": round(accuracy_score(y_test, pipeline.predict(X_test)), 4),
        "roc_auc": round(roc_auc_score(y_test, pipeline.predict_proba(X_test)[:, 1]), 4),
        "n": len(y_test),
    }

    if test_metrics["roc_auc"] <= 0.50:
        raise ValueError(
            f"{version} test ROC-AUC {test_metrics['roc_auc']:.4f} did not exceed 0.50. "
            "Check feature quality or data coverage."
        )

    MODELS_DIR.mkdir(exist_ok=True)
    with open(MODELS_DIR / f"model_{version}.pkl", "wb") as f:
        pickle.dump(pipeline, f)

    model_meta = {
        "version": version,
        "algorithm": algorithm_name,
        "features": feature_cols,
        "hyperparameters": hyperparams,
        "label_forward_days": FORWARD_DAYS,
        "label_threshold_pct": LABEL_THRESHOLD * 100,
        "train_accuracy": train_metrics["accuracy"],
        "train_roc_auc": train_metrics["roc_auc"],
        "train_n": train_metrics["n"],
        "test_accuracy": test_metrics["accuracy"],
        "test_roc_auc": test_metrics["roc_auc"],
        "test_n": test_metrics["n"],
        "training_date": datetime.datetime.utcnow().isoformat(),
    }
    with open(MODELS_DIR / f"model_{version}.json", "w") as f:
        json.dump(model_meta, f, indent=2)

    print(f"\n{version} ({algorithm_name}) trained:")
    print(f"  Train: n={train_metrics['n']}, accuracy={train_metrics['accuracy']:.4f}, ROC-AUC={train_metrics['roc_auc']:.4f}")
    print(f"  Test:  n={test_metrics['n']}, accuracy={test_metrics['accuracy']:.4f}, ROC-AUC={test_metrics['roc_auc']:.4f}")
    return model_meta


def main(db_path: str = "data/trading.db") -> None:
    print("Loading data...")
    raw_df = _load_all_data(db_path)

    # v2: Momentum + Volume, LogisticRegression
    v2_params = {"C": 0.1, "random_state": 42, "max_iter": 1000}
    _train_and_save(
        raw_df,
        FEATURE_COLS_V2,
        build_features_v2,
        Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(**v2_params))]),
        version="v2",
        algorithm_name="LogisticRegression",
        hyperparams=v2_params,
    )

    # v3: Volatility + Mean-reversion, RandomForestClassifier
    v3_params = {"n_estimators": 100, "max_depth": 5, "random_state": 42}
    _train_and_save(
        raw_df,
        FEATURE_COLS_V3,
        build_features_v3,
        Pipeline([("scaler", StandardScaler()), ("clf", RandomForestClassifier(**v3_params))]),
        version="v3",
        algorithm_name="RandomForestClassifier",
        hyperparams=v3_params,
    )

    print("\nDone. Models saved to models/")


if __name__ == "__main__":
    main()
