import sqlalchemy as sa
import pandas as pd

from data.schema import market_data, metadata

FORWARD_DAYS = 5
LABEL_THRESHOLD = 0.02

FEATURE_COLS = [
    "return_1d",
    "return_5d",
    "return_10d",
    "vol_ratio_5d",
    "price_to_ma5",
    "price_to_ma10",
    "rsi_14",
]


def load_market_data(db_path: str = "data/trading.db") -> pd.DataFrame:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    with engine.connect() as conn:
        rows = conn.execute(sa.select(market_data)).fetchall()
    return pd.DataFrame(rows, columns=[c.name for c in market_data.columns])


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["ticker", "date"]).copy()
    parts = []
    for _, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("date").copy()
        g["return_1d"] = g["close"].pct_change(1)
        g["return_5d"] = g["close"].pct_change(5)
        g["return_10d"] = g["close"].pct_change(10)
        g["vol_ratio_5d"] = g["volume"] / g["volume"].rolling(5).mean()
        g["price_to_ma5"] = g["close"] / g["close"].rolling(5).mean() - 1
        g["price_to_ma10"] = g["close"] / g["close"].rolling(10).mean() - 1
        g["rsi_14"] = _rsi(g["close"], 14)
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    out = out.dropna(subset=FEATURE_COLS)
    return out[["ticker", "date", "close"] + FEATURE_COLS].reset_index(drop=True)


def build_labels(
    df: pd.DataFrame,
    forward_days: int = FORWARD_DAYS,
    threshold: float = LABEL_THRESHOLD,
) -> pd.DataFrame:
    parts = []
    for _, grp in df.groupby("ticker", sort=False):
        g = grp.sort_values("date").copy()
        g["_future_close"] = g["close"].shift(-forward_days)
        g = g.dropna(subset=["_future_close"])
        g["label"] = (g["_future_close"] >= g["close"] * (1 + threshold)).astype(int)
        g = g.drop(columns=["_future_close"])
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def build_labeled_dataset(
    db_path: str = "data/trading.db",
) -> tuple[pd.DataFrame, pd.Series]:
    raw = load_market_data(db_path)
    if raw.empty:
        raise ValueError("No market data found in database. Run ingestion first.")
    features = build_features(raw)
    labeled = build_labels(features)
    return labeled[FEATURE_COLS], labeled["label"]
