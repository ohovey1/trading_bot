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

`v1` — saved at `models/model_v1.pkl`
