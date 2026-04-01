# Model Card — Trade Signal Classifier v1

## Model Type

Scikit-learn Pipeline: `StandardScaler` → `LogisticRegression`

Parameters: `C=0.1`, `random_state=42`, `max_iter=1000`

## Features

| Feature | Description |
|---|---|
| sma_10 | 10-day simple moving average of close |
| sma_30 | 30-day simple moving average of close |
| sma_ratio | sma_10 / sma_30 (trend direction) |
| rsi_14 | 14-period RSI of close (momentum) |
| volume_ratio | volume / 20-day average volume (relative activity) |
| atr_14 | 14-period average true range (volatility) |
| price_change_5d | (close − close[5d ago]) / close[5d ago] (short-term momentum) |
| close_vs_high_20 | close / 20-day rolling high (distance from recent peak) |

## Label Definition

Binary: `1` if the close price 10 trading days forward is ≥3% higher than the current close, else `0`.

The last 10 rows per ticker are dropped to prevent future data leakage.

## Data

- **Universe:** 46 active small-cap tickers (Russell 2000 subset)
- **Date range:** 2024-04-01 to 2026-03-30 (~2 years of daily OHLCV)
- **Total samples after feature engineering:** 21,128

## Train/Test Split

Chronological split (no shuffle): last 20% of rows by date form the test set.

- **Train:** 16,902 rows
- **Test:** 4,226 rows

## Metrics

| Split | Accuracy | ROC-AUC |
|---|---|---|
| Train | 0.6658 | 0.5865 |
| Test | 0.6619 | 0.5192 |

Test class distribution: ~66% negative (0), ~34% positive (1).

## Limitations

This is an intentionally minimal baseline. Key limitations:
- Logistic regression is a linear model; it cannot capture non-linear price patterns
- Label class imbalance (~2:1) suppresses recall on the positive class
- No walk-forward validation — single chronological split only
- Features are all price/volume derived; no macro or sector signals

## Version

`v1` — saved at `models/model_v1.pkl` — **production model**

---

# Model Card — Trade Signal Classifier v2

## Model Type

Scikit-learn Pipeline: `StandardScaler` → `LogisticRegression`

Parameters: `C=0.1`, `random_state=42`, `max_iter=1000`

## Feature Rationale

v2 focuses on **momentum and volume** signals. The goal is to capture buying pressure through volume flow (OBV, VPT) and short-to-medium term directional momentum (MACD, 3d/7d price change). The SMA-based features from v1 were dropped in favor of MACD which more directly captures momentum crossovers.

## Features

| Feature | Description |
|---|---|
| macd_line | EMA(12) − EMA(26) of close (momentum divergence) |
| macd_signal | 9-day EMA of MACD line (signal line) |
| obv | On-balance volume — cumulative volume-weighted direction |
| volume_price_trend | Running sum of (pct_change × volume) — volume-weighted momentum |
| price_change_3d | (close − close[3d ago]) / close[3d ago] |
| price_change_7d | (close − close[7d ago]) / close[7d ago] |
| rsi_14 | 14-period RSI of close |
| volume_ratio | volume / 20-day average volume |

## Label Definition

Same as v1: binary `1` if close 10 trading days forward is ≥3% higher than current close.

## Metrics

| Split | n | Accuracy | ROC-AUC |
|---|---|---|---|
| Train | 54,723 | 0.6395 | 0.5372 |
| Test | 13,681 | 0.6378 | 0.5334 |

## Version

`v2` — saved at `models/model_v2.pkl` — comparison only

---

# Model Card — Trade Signal Classifier v3

## Model Type

Scikit-learn Pipeline: `StandardScaler` → `RandomForestClassifier`

Parameters: `n_estimators=100`, `max_depth=5`, `random_state=42`

## Feature Rationale

v3 focuses on **volatility and mean-reversion** signals. The hypothesis is that stocks trading near extremes (Bollinger Band boundaries, 52-week highs/lows) or in high-volatility regimes have predictable near-term behavior. RandomForest was chosen here as it can capture non-linear interactions between volatility and distance-from-mean features more naturally than logistic regression.

## Features

| Feature | Description |
|---|---|
| bb_position | (close − BB_lower) / (BB_upper − BB_lower) — position within Bollinger Bands (20d, 2σ) |
| bb_width | (BB_upper − BB_lower) / SMA_20 — normalized band width (volatility expansion) |
| hist_vol_20 | 20-day std of log returns (realized volatility) |
| dist_52w_high | close / 52-week rolling high (distance from peak) |
| dist_52w_low | close / 52-week rolling low (distance from trough) |
| rsi_14 | 14-period RSI of close (momentum / mean-reversion signal) |
| atr_ratio | ATR(14) / close (volatility normalized by price) |
| close_vs_sma_50 | close / 50-day SMA (distance from medium-term mean) |

## Label Definition

Same as v1: binary `1` if close 10 trading days forward is ≥3% higher than current close.

## Metrics

| Split | n | Accuracy | ROC-AUC |
|---|---|---|---|
| Train | 49,933 | 0.6408 | 0.6234 |
| Test | 12,484 | 0.6232 | 0.5415 |

The higher train ROC-AUC relative to test (0.623 vs 0.542) indicates mild overfitting from the forest — max_depth=5 limits this but does not eliminate it.

## Version

`v3` — saved at `models/model_v3.pkl` — comparison only
