import streamlit as st

st.set_page_config(
    page_title="Trading Signal System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Trading Signal System")
st.markdown(
    "A personal ML-driven system that generates trade signals for small-cap stocks "
    "using logistic regression, automated outcome tracking, and daily pipeline orchestration."
)

st.divider()

st.subheader("Pages")

pages = [
    ("pages/1_Overview.py",    "Overview",      "Project summary, system architecture, and end-to-end flow"),
    ("pages/2_Data.py",        "Data",          "Ticker universe, OHLCV coverage, and data quality notes"),
    ("pages/3_Model.py",       "Model",         "Feature engineering, model versions, and comparison metrics"),
    ("pages/4_Signals.py",     "Signals",       "Operational heartbeat — open signals, recommendations, and past performance"),
    ("pages/5_Backtesting.py", "Backtesting",   "Historical simulation results, equity curve, and outcome breakdown"),
    ("pages/6_Pipeline.py",    "Pipeline",      "Prefect flow schedules and orchestration details"),
]

for path, label, description in pages:
    col_link, col_desc = st.columns([1, 4])
    with col_link:
        st.page_link(path, label=f"**{label}**")
    with col_desc:
        st.markdown(description)
