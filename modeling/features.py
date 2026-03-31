import pandas as pd

FEATURE_COLS = [
    "sma_10",
    "sma_30",
    "sma_ratio",
    "rsi_14",
    "volume_ratio",
    "atr_14",
    "price_change_5d",
    "close_vs_high_20",
]

FORWARD_DAYS = 10
LABEL_THRESHOLD = 0.03


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(window).mean()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build features and label for a per-ticker OHLCV DataFrame.

    Returns a DataFrame with FEATURE_COLS + 'label'. The last FORWARD_DAYS rows
    per ticker are dropped to prevent future data leakage.
    """
    parts = []
    for _, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("date").copy()

        g["sma_10"] = g["close"].rolling(10).mean()
        g["sma_30"] = g["close"].rolling(30).mean()
        g["sma_ratio"] = g["sma_10"] / g["sma_30"]
        g["rsi_14"] = _rsi(g["close"], 14)
        g["volume_ratio"] = g["volume"] / g["volume"].rolling(20).mean()
        g["atr_14"] = _atr(g, 14)
        g["price_change_5d"] = (g["close"] - g["close"].shift(5)) / g["close"].shift(5)
        g["close_vs_high_20"] = g["close"] / g["close"].rolling(20).max()

        # Label: 1 if close FORWARD_DAYS ahead is >= LABEL_THRESHOLD higher
        g["_future_close"] = g["close"].shift(-FORWARD_DAYS)
        g["label"] = (g["_future_close"] >= g["close"] * (1 + LABEL_THRESHOLD)).astype(int)
        g = g.drop(columns=["_future_close"])

        # Drop last FORWARD_DAYS rows (no future close available) and NaN feature rows
        g = g.iloc[:-FORWARD_DAYS]
        g = g.dropna(subset=FEATURE_COLS)

        parts.append(g)

    out = pd.concat(parts, ignore_index=True)
    return out[["ticker", "date", "close"] + FEATURE_COLS + ["label"]].reset_index(drop=True)
