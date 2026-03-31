import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from modeling.features import build_features, build_labels, FEATURE_COLS
import modeling.registry as reg


def _make_ohlcv(n: int = 60, ticker: str = "TEST") -> pd.DataFrame:
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


def test_build_features_returns_expected_columns_and_no_nans():
    df = _make_ohlcv(60)
    result = build_features(df)
    for col in FEATURE_COLS:
        assert col in result.columns, f"Missing feature: {col}"
    assert result[FEATURE_COLS].isna().sum().sum() == 0
    assert len(result) > 0


def test_build_labels_produces_binary_no_nans():
    df = _make_ohlcv(60)
    feat = build_features(df)
    labeled = build_labels(feat)
    assert "label" in labeled.columns
    assert labeled["label"].isna().sum() == 0
    assert set(labeled["label"].unique()).issubset({0, 1})


def test_build_labels_drops_rows_without_forward_window():
    df = _make_ohlcv(60)
    feat = build_features(df)
    labeled = build_labels(feat, forward_days=5)
    assert len(labeled) == len(feat) - 5


def test_train_produces_fitted_model():
    df = _make_ohlcv(100)
    feat = build_features(df)
    labeled = build_labels(feat)
    X = labeled[FEATURE_COLS]
    y = labeled["label"]

    split = int(len(X) * 0.8)
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X.iloc[:split], y.iloc[:split])

    preds = model.predict(X.iloc[split:])
    assert len(preds) == len(X.iloc[split:])
    assert set(preds).issubset({0, 1})


def test_save_load_roundtrip_preserves_predictions(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "MODELS_DIR", tmp_path)

    df = _make_ohlcv(100)
    feat = build_features(df)
    labeled = build_labels(feat)
    X = labeled[FEATURE_COLS]
    y = labeled["label"]

    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X, y)
    original_preds = model.predict(X)

    reg.save_model(model, {"features": FEATURE_COLS, "test_accuracy": 0.5})
    loaded = reg.load_latest_model()
    loaded_preds = loaded.predict(X)

    np.testing.assert_array_equal(original_preds, loaded_preds)
