import numpy as np
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


# ---------------------------------------------------------------------------
# v2 — Momentum + Volume feature set
# ---------------------------------------------------------------------------

FEATURE_COLS_V2 = [
    "macd_line",
    "macd_signal",
    "obv",
    "volume_price_trend",
    "price_change_3d",
    "price_change_7d",
    "rsi_14",
    "volume_ratio",
]


def build_features_v2(df: pd.DataFrame) -> pd.DataFrame:
    """Momentum + Volume feature set for v2 model."""
    parts = []
    for _, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("date").copy()

        ema12 = g["close"].ewm(span=12, adjust=False).mean()
        ema26 = g["close"].ewm(span=26, adjust=False).mean()
        g["macd_line"] = ema12 - ema26
        g["macd_signal"] = g["macd_line"].ewm(span=9, adjust=False).mean()

        direction = np.sign(g["close"].diff().fillna(0))
        g["obv"] = (direction * g["volume"]).cumsum()

        pct_change = g["close"].pct_change().fillna(0)
        g["volume_price_trend"] = (pct_change * g["volume"]).cumsum()

        g["price_change_3d"] = (g["close"] - g["close"].shift(3)) / g["close"].shift(3)
        g["price_change_7d"] = (g["close"] - g["close"].shift(7)) / g["close"].shift(7)
        g["rsi_14"] = _rsi(g["close"], 14)
        g["volume_ratio"] = g["volume"] / g["volume"].rolling(20).mean()

        g["_future_close"] = g["close"].shift(-FORWARD_DAYS)
        g["label"] = (g["_future_close"] >= g["close"] * (1 + LABEL_THRESHOLD)).astype(int)
        g = g.drop(columns=["_future_close"])

        g = g.iloc[:-FORWARD_DAYS]
        g = g.dropna(subset=FEATURE_COLS_V2)
        parts.append(g)

    out = pd.concat(parts, ignore_index=True)
    return out[["ticker", "date", "close"] + FEATURE_COLS_V2 + ["label"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# v3 — Volatility + Mean-reversion feature set
# ---------------------------------------------------------------------------

FEATURE_COLS_V3 = [
    "bb_position",
    "bb_width",
    "hist_vol_20",
    "dist_52w_high",
    "dist_52w_low",
    "rsi_14",
    "atr_ratio",
    "close_vs_sma_50",
]


def build_features_v3(df: pd.DataFrame) -> pd.DataFrame:
    """Volatility + Mean-reversion feature set for v3 model."""
    parts = []
    for _, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("date").copy()

        sma20 = g["close"].rolling(20).mean()
        std20 = g["close"].rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_range = (bb_upper - bb_lower).replace(0, np.nan)
        g["bb_position"] = (g["close"] - bb_lower) / bb_range
        g["bb_width"] = bb_range / sma20

        log_ret = np.log(g["close"] / g["close"].shift(1))
        g["hist_vol_20"] = log_ret.rolling(20).std()

        rolling_max = g["close"].rolling(252, min_periods=60).max()
        rolling_min = g["close"].rolling(252, min_periods=60).min().replace(0, np.nan)
        g["dist_52w_high"] = g["close"] / rolling_max
        g["dist_52w_low"] = g["close"] / rolling_min

        g["rsi_14"] = _rsi(g["close"], 14)
        g["atr_ratio"] = _atr(g, 14) / g["close"].replace(0, np.nan)
        g["close_vs_sma_50"] = g["close"] / g["close"].rolling(50).mean()

        g["_future_close"] = g["close"].shift(-FORWARD_DAYS)
        g["label"] = (g["_future_close"] >= g["close"] * (1 + LABEL_THRESHOLD)).astype(int)
        g = g.drop(columns=["_future_close"])

        g = g.iloc[:-FORWARD_DAYS]
        g = g.dropna(subset=FEATURE_COLS_V3)
        parts.append(g)

    out = pd.concat(parts, ignore_index=True)
    return out[["ticker", "date", "close"] + FEATURE_COLS_V3 + ["label"]].reset_index(drop=True)
