import streamlit as st
import pandas as pd
from pathlib import Path

from dashboard.utils.db import get_model_versions
from dashboard.utils.paths import MODEL_CARD_PATH

st.title("Feature Engineering & Model")

# --- Feature table ---
st.subheader("Features")

features = pd.DataFrame([
    {"Feature": "sma_10",          "Type": "Trend",     "Description": "10-day simple moving average of close; captures short-term price trend"},
    {"Feature": "sma_30",          "Type": "Trend",     "Description": "30-day simple moving average of close; captures medium-term trend"},
    {"Feature": "sma_ratio",       "Type": "Momentum",  "Description": "sma_10 / sma_30; >1 indicates uptrend, <1 indicates downtrend"},
    {"Feature": "rsi_14",          "Type": "Momentum",  "Description": "14-day RSI; overbought/oversold oscillator (70+ overbought, 30- oversold)"},
    {"Feature": "volume_ratio",    "Type": "Activity",  "Description": "Today's volume / 20-day average volume; flags unusual trading activity"},
    {"Feature": "atr_14",          "Type": "Volatility","Description": "14-day average true range; measures daily price volatility in dollar terms"},
    {"Feature": "price_change_5d", "Type": "Momentum",  "Description": "(close − close 5 days ago) / close 5 days ago; 5-day price momentum"},
    {"Feature": "close_vs_high_20","Type": "Strength",  "Description": "close / 20-day rolling high; proximity to recent peak (1.0 = at the high)"},
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

# --- Model versions table ---
st.subheader("Model Versions")

versions = get_model_versions()
if not versions:
    st.info("No model versions found in models/.")
else:
    rows = []
    for v in versions:
        rows.append({
            "Version": v.get("version", ""),
            "Type": "LogisticRegression + StandardScaler",
            "Training Date": str(v.get("training_date", ""))[:10],
            "Train ROC-AUC": round(v.get("train_roc_auc", 0), 4),
            "Test ROC-AUC": round(v.get("test_roc_auc", 0), 4),
            "Train N": v.get("train_n", ""),
            "Test N": v.get("test_n", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# --- Model card ---
st.subheader("Model Card")
if MODEL_CARD_PATH.exists():
    st.markdown(MODEL_CARD_PATH.read_text())
else:
    st.warning(f"MODEL_CARD.md not found at {MODEL_CARD_PATH}")
