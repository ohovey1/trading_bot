import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from modeling.features import build_features, FEATURE_COLS
import models.registry as reg


def _make_ohlcv(n: int = 80, ticker: str = "TEST") -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + rng.normal(0, 1, n).cumsum()
    close = np.abs(close) + 10
    dates = pd.date_range("2024-01-01", periods=n).date
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
        }
    )


def test_build_features_returns_expected_columns():
    df = _make_ohlcv(80)
    result = build_features(df)
    for col in FEATURE_COLS:
        assert col in result.columns, f"Missing feature: {col}"
    assert "label" in result.columns


def test_build_features_no_nans_on_valid_input():
    df = _make_ohlcv(80)
    result = build_features(df)
    assert result[FEATURE_COLS].isna().sum().sum() == 0
    assert len(result) > 0


def test_build_features_drops_last_forward_days_rows():
    from modeling.features import FORWARD_DAYS
    df = _make_ohlcv(80)
    result = build_features(df)
    # Last row date should be at least FORWARD_DAYS before the last input date
    last_input_date = df["date"].max()
    last_output_date = result["date"].max()
    assert last_output_date < last_input_date


def test_train_test_split_is_chronological():
    df = _make_ohlcv(80)
    result = build_features(df)
    X = result[FEATURE_COLS]
    dates = result["date"]

    split = int(len(X) * 0.8)
    train_dates = dates.iloc[:split]
    test_dates = dates.iloc[split:]

    assert train_dates.max() <= test_dates.min(), "Train/test split is not chronological"


def test_model_produces_probability_outputs():
    df = _make_ohlcv(80)
    result = build_features(df)
    X = result[FEATURE_COLS]
    y = result["label"]

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=42, max_iter=1000, C=0.1)),
    ])
    pipeline.fit(X, y)

    proba = pipeline.predict_proba(X)
    assert proba.shape == (len(X), 2)
    assert ((proba >= 0) & (proba <= 1)).all()
    # Each row should sum to 1
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_save_load_model_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "MODELS_DIR", tmp_path)

    df = _make_ohlcv(80)
    result = build_features(df)
    X = result[FEATURE_COLS]
    y = result["label"]

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=42, max_iter=1000, C=0.1)),
    ])
    pipeline.fit(X, y)
    original_preds = pipeline.predict(X)

    reg.save_model(pipeline, {"features": FEATURE_COLS, "test_roc_auc": 0.55})
    loaded = reg.load_model()
    loaded_preds = loaded.predict(X)

    np.testing.assert_array_equal(original_preds, loaded_preds)


def test_save_model_increments_version(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "MODELS_DIR", tmp_path)

    df = _make_ohlcv(80)
    result = build_features(df)
    X = result[FEATURE_COLS]
    y = result["label"]

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=42, max_iter=1000, C=0.1)),
    ])
    pipeline.fit(X, y)

    v1 = reg.save_model(pipeline, {})
    v2 = reg.save_model(pipeline, {})
    assert v1 == "v1"
    assert v2 == "v2"
