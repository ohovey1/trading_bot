import streamlit as st
import pandas as pd
import plotly.express as px

from dashboard.utils.db import get_model_versions
from dashboard.utils.paths import MODEL_CARD_PATH

st.title("Feature Engineering & Model")

# --- Why these models? ---
st.subheader("Why these models?")

st.markdown("""
**Logistic regression as the baseline**

Logistic regression was chosen as the first model because it is fast to train,
fully reproducible, and easy to interpret. Given a feature vector, it outputs a
probability directly -- no calibration step needed. For a binary classification
task like this (will the stock be up 3% in 10 days?), it sets a clear,
defensible performance floor before any complexity is introduced.

**What the label means in practice**

A label of `1` is assigned to any row where the closing price 10 trading days
later is at least 3% above the closing price today. Everything else is `0`. In
practice, this means the model is trying to identify stocks that are likely to
move meaningfully upward over a two-week horizon -- not just drift slightly higher.
The 3% threshold is intentionally set above typical daily noise.

**What the features measure**

The features are all derived from price and volume data already in the database --
no external data sources required. They fall into four categories:

- **Trend** -- moving averages (SMA-10, SMA-30) and their ratio tell the model
  whether the stock is trading above or below its recent average trajectory.
- **Momentum** -- RSI-14, short-term price changes (3d, 5d, 7d), and MACD
  measure the rate and direction of recent price movement.
- **Volatility** -- ATR-14, Bollinger Band width, and historical volatility
  capture how much the price is moving day to day. Higher volatility can mean
  more opportunity but also more risk.
- **Strength / position** -- metrics like `close_vs_high_20`, distance from
  52-week high/low, and SMA-50 proximity describe where the stock sits relative
  to recent price extremes.

Each model version uses a different feature set to test whether a different view
of the data improves predictive performance.
""")

st.divider()

# --- Feature table ---
st.subheader("Features (v1 baseline)")

features = pd.DataFrame([
    {"Feature": "sma_10",           "Type": "Trend",      "Description": "10-day simple moving average of close; captures short-term price trend"},
    {"Feature": "sma_30",           "Type": "Trend",      "Description": "30-day simple moving average of close; captures medium-term trend"},
    {"Feature": "sma_ratio",        "Type": "Momentum",   "Description": "sma_10 / sma_30; above 1 indicates uptrend, below 1 indicates downtrend"},
    {"Feature": "rsi_14",           "Type": "Momentum",   "Description": "14-day RSI; overbought/oversold oscillator (70+ overbought, 30- oversold)"},
    {"Feature": "volume_ratio",     "Type": "Activity",   "Description": "Today's volume / 20-day average volume; flags unusual trading activity"},
    {"Feature": "atr_14",           "Type": "Volatility", "Description": "14-day average true range; measures daily price volatility in dollar terms"},
    {"Feature": "price_change_5d",  "Type": "Momentum",   "Description": "(close - close 5 days ago) / close 5 days ago; 5-day price momentum"},
    {"Feature": "close_vs_high_20", "Type": "Strength",   "Description": "close / 20-day rolling high; proximity to recent peak (1.0 = at the high)"},
])

st.dataframe(features, use_container_width=True, hide_index=True)

# --- Label definition ---
st.subheader("Label Definition")
st.markdown("""
**Binary classification target**

A label of `1` is assigned if the closing price **10 trading days ahead** is at least
**3% higher** than the closing price on the signal date. All other rows receive `0`.

The last 10 rows per ticker are dropped at training time to prevent future data leakage.

This formulation aligns the model directly with the signal's profit objective: the 5%
upside target and 3% stop-loss are downstream of this label, not upstream.
""")

st.divider()

# --- Model Comparison ---
st.subheader("Model Comparison")

versions = get_model_versions()
if not versions:
    st.info("No model versions found in models/.")
else:
    rows = []
    for v in versions:
        algorithm = v.get("algorithm", "LogisticRegression")
        rows.append({
            "Version":         v.get("version", ""),
            "Algorithm":       algorithm,
            "Feature Count":   len(v.get("features", [])),
            "Train Accuracy":  round(v.get("train_accuracy", 0), 4),
            "Test Accuracy":   round(v.get("test_accuracy", 0), 4),
            "Train ROC-AUC":   round(v.get("train_roc_auc", 0), 4),
            "Test ROC-AUC":    round(v.get("test_roc_auc", 0), 4),
            "Training Date":   str(v.get("training_date", ""))[:10],
        })

    comparison_df = pd.DataFrame(rows)
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    # Grouped bar chart: Test Accuracy vs Test ROC-AUC per version
    chart_df = comparison_df[["Version", "Test Accuracy", "Test ROC-AUC"]].melt(
        id_vars="Version",
        value_vars=["Test Accuracy", "Test ROC-AUC"],
        var_name="Metric",
        value_name="Score",
    )
    fig = px.bar(
        chart_df,
        x="Version",
        y="Score",
        color="Metric",
        barmode="group",
        title="Test Accuracy and Test ROC-AUC by Model Version",
        labels={"Score": "Score", "Version": "Model Version"},
        color_discrete_map={"Test Accuracy": "#3498db", "Test ROC-AUC": "#e67e22"},
    )
    fig.update_yaxes(range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Model card ---
st.subheader("Model Card")
if MODEL_CARD_PATH.exists():
    st.markdown(MODEL_CARD_PATH.read_text())
else:
    st.warning(f"MODEL_CARD.md not found at {MODEL_CARD_PATH}")
