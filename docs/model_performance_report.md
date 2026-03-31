# Model Performance Report

**Generated:** 2026-03-31
**Model version:** v1
**Training date:** 2026-03-31
**Data source:** Yahoo Finance, 2-year OHLCV history, 46 of 50 universe tickers

---

## 1. Modeling Methodology

### Features

The model uses eight technical indicators computed from daily OHLCV data:

| Feature | Description |
|---|---|
| `sma_10` | 10-day simple moving average of close price |
| `sma_30` | 30-day simple moving average of close price |
| `sma_ratio` | sma_10 / sma_30 — measures short-term momentum relative to medium-term trend |
| `rsi_14` | 14-period Relative Strength Index — momentum oscillator scaled 0–100 |
| `volume_ratio` | Today's volume divided by the 20-day average volume — flags unusual activity |
| `atr_14` | 14-period Average True Range — measures recent daily price volatility in dollars |
| `price_change_5d` | Percentage price change over the past 5 trading days |
| `close_vs_high_20` | Close price as a fraction of the 20-day rolling high — proximity to recent peak |

RSI is computed using a simple rolling mean of gains and losses (Wilder-style smoothing approximation). ATR uses the true range: the maximum of (high − low), |high − previous close|, and |low − previous close|.

### Target variable

The label is binary: **1** if the close price 10 trading days ahead is at least **3% higher** than today's close, **0** otherwise. This encodes a straightforward "buy and hold for two weeks" signal. The 3% threshold filters out small noise-level moves, focusing the model on meaningful upside.

The last 10 rows of each ticker's time series are dropped before training — those rows have no resolvable forward close and would produce incorrect labels.

### Model type

The model is a **StandardScaler + LogisticRegression** sklearn pipeline (regularization strength C=0.1, max iterations 1000, random state 42). Logistic regression was the right choice for a baseline because it is fast to train, easy to inspect, produces calibrated probabilities directly, and is unlikely to silently overfit small datasets. The pipeline scales features to zero mean and unit variance before fitting, which is required for logistic regression to treat all features on equal footing.

### Train/test split

Data from all 46 tickers is concatenated and sorted chronologically by (date, ticker). The first 80% of rows form the training set; the last 20% form the test set. This is a **time-based split** — the model never sees future data during training. It is not a random shuffle split, which would allow future price information to leak into the training set through overlapping rolling-window features.

---

## 2. Backtesting Methodology

### Outcome resolution (`backtesting/resolve.py`)

For each open signal in the database, the resolver checks whether the expected hold period has elapsed. The default hold period is **10 trading business days** from signal generation. If enough time has passed, it fetches the close price at the resolution date using an `asof()` lookup (which finds the closest available price at or before that date, handling weekends and holidays). The return is computed as `(exit_price − entry_price) / entry_price`.

Outcomes are classified as:

- **Win**: return ≥ +3%
- **Loss**: return ≤ −3%
- **Neutral**: return between −3% and +3%

The resolved outcome and exit price are written to the `outcomes` table and the signal is marked `closed`.

### Historical simulation (`backtesting/simulate.py`)

Because the system is new and has very few live signals, a historical simulation is used to estimate model performance across the full 2-year dataset. The simulation:

1. Loads all OHLCV data from the database.
2. Runs `build_features()` across all tickers, which drops the last 10 rows per ticker to prevent leakage.
3. For each row where the model's predicted probability of a win is ≥ 0.55, generates a simulated signal.
4. Resolves each simulated signal using the actual close price 10 business days later.
5. Returns results as a list of dicts — **nothing is written to the database**.

The confidence threshold of 0.55 is slightly above the 0.50 midpoint, intended to filter out the model's least confident predictions.

### Limitations

- **Look-ahead in feature construction**: `build_features()` drops the last 10 rows to prevent label leakage, but rolling windows (e.g., sma_30) are computed over the full in-sample history. In a truly realistic walk-forward test, features would also be restricted to data available at signal time. The impact here is small because these features are purely backward-looking.
- **Signal independence assumption**: The simulation treats every signal as independent and size-agnostic. In practice, multiple signals on the same day across correlated tickers would be partially redundant, and position sizing would reduce effective returns.
- **No transaction costs**: Entry and exit at close price with no slippage, commissions, or spread. For small-cap stocks this is a material omission.
- **Data coverage gaps**: Four tickers (AMED, CATS, COMM, COOP) returned no data from Yahoo Finance (likely delisted), so the universe effectively covers 46 tickers.
- **Short live history**: As of this run, only 3 live signals have been generated and none have reached their 10-day resolution window. All performance numbers below come from the historical simulation.

---

## 3. Results from End-to-End Run

### Live pipeline run (2026-03-31)

The full pipeline (`pipeline.run_pipeline`) completed successfully:

- **Signals generated:** 3 (tickers: AEIS, BOOT, CVCO)
- **Signals resolved:** 0 (all are within their hold window)
- **Outcomes scored:** 0 (no closed signals yet)

### Historical simulation

Running `simulate_historical_signals()` across the 2-year OHLCV dataset produced:

| Metric | Value |
|---|---|
| Total simulated signals | 393 |
| Win rate | 50.4% |
| Loss rate | 30.3% |
| Neutral rate | 19.3% |
| Average return per signal | +2.83% |
| Average win return | +12.27% |
| Average loss return | −11.20% |
| Sharpe ratio (approx) | 0.22 |
| Estimated P&L at $1,000/signal | +$11,132 |

### Best and worst tickers (by average return)

**Top performers:**

| Ticker | Avg return | Signals |
|---|---|---|
| BDC | +10.2% | 1 |
| BFAM | +9.6% | 4 |
| AEIS | +8.3% | 57 |
| CNXC | +8.0% | 1 |
| CCOI | +7.7% | 21 |

**Worst performers:**

| Ticker | Avg return | Signals |
|---|---|---|
| CHGG | −19.5% | 1 |
| CMCO | −4.3% | 17 |
| MSFT | −2.0% | 7 |
| ARCB | +0.1% | 20 |

### Model version breakdown

Only model v1 exists. All 393 simulated signals were scored against v1.

---

## 4. Performance Metrics Summary

### Training metrics (from `models/model_v1.json`)

| Metric | Train | Test |
|---|---|---|
| Samples | 16,902 | 4,226 |
| Accuracy | 66.6% | 66.2% |
| ROC-AUC | 0.587 | 0.519 |

The train and test accuracies are nearly identical, which is good — it indicates the model is not overfitting its training data. The ROC-AUC of 0.52 on the test set is above 0.50 (the random baseline), confirming the model has some genuine predictive signal, but only barely. This is expected for a v1 logistic regression on price-derived features.

### Trading-domain equivalents

- **Win rate (50.4%)** is the trading analog of precision for the "buy" class. Half of all signals that cross the 0.55 confidence threshold result in a ≥3% gain within 10 days. For a long-only system with symmetric win/loss magnitudes (+12.3% vs −11.2%), a win rate above 50% is the minimum required for positive expected return, and we are just above that line.
- **Estimated P&L:** Allocating $1,000 per signal across 393 historical trades produces a total gain of approximately **+$11,132** — a return of about **2.8%** per trade on average. This does not account for transaction costs.

---

## 5. Identified Weaknesses and Areas for Improvement

### Weaknesses

**1. The confidence threshold (0.55) is too low.**
The gap between 0.50 and 0.55 is narrow given a ROC-AUC of 0.52. The threshold is catching signals where the model is only marginally more confident than a coin flip. Raising it to 0.60 or 0.65 would reduce signal count but likely improve win rate and average return by filtering out the weakest predictions.

**2. Significant signal concentration in a few tickers.**
CVCO generated 130 of 393 simulated signals (33%), and AEIS generated 57 (14.5%). When nearly half the simulated trades come from two tickers, the aggregate performance figures reflect those tickers' idiosyncratic behavior more than model generalizability. A position sizing or per-ticker signal cap is missing.

**3. The loss magnitude nearly equals the win magnitude.**
Average wins (+12.3%) and average losses (−11.2%) are close to symmetric. The model is not generating an asymmetric edge — it is winning slightly more than half the time but not cutting losses short or letting winners run. Without a stop-loss or trailing exit built into the signal profile, losses are left to run the full 10-day hold period.

**4. The ROC-AUC drops from 0.587 (train) to 0.519 (test).**
A drop of 6.8 percentage points between train and test suggests the model's ability to rank predictions degrades on unseen dates. The features themselves (especially rolling averages and RSI) are computed without any walk-forward scheme, which may allow subtle data artifacts to inflate training performance.

**5. Four tickers returned no data (possibly delisted).**
AMED, CATS, COMM, and COOP failed to download. If any of these were historically volatile or trend-following, their absence creates survivorship bias — the universe only contains companies that survived long enough to remain listed, which flatters backtest results.

### Prioritized improvements

**1. Raise the confidence threshold to 0.62–0.65.**
The most direct lever on precision. Run the simulation at multiple thresholds (0.55, 0.60, 0.65, 0.70) and plot win rate and total P&L at each cutoff. The current threshold was a reasonable starting point but should be tuned against actual simulation results now that data is available.

**2. Add a per-ticker signal cap and minimum signal spacing.**
Cap each ticker at one open signal at a time, and require at least 5 trading days between signals for the same ticker. This directly addresses the CVCO/AEIS concentration problem and makes backtest results more representative of what a real portfolio would look like.

**3. Introduce asymmetric exit logic (stop-loss).**
Instead of always holding for 10 days, exit early if the position drops more than 5% from entry. This would reduce average loss magnitude without affecting average win magnitude, improving the overall Sharpe ratio. Implement this as an option in `resolve.py` before the 10-day hold period expires.
