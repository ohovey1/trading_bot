import streamlit as st
import plotly.graph_objects as go

st.title("Project Overview")

st.markdown("""
This system ingests daily OHLCV data for a 150-ticker Russell 2000 small-cap universe,
engineers technical features, trains a classifier, generates trade signals with
entry/target/stop prices, re-evaluates open positions intraday, and automatically
tracks outcomes — no manual labeling required.
""")

# --- Architecture diagram (Plotly) ---
st.subheader("Architecture")

steps = [
    ("Data\nIngestion",   "#3498db", "Fetch daily OHLCV bars\nfrom Yahoo Finance"),
    ("Feature\nEngineering", "#27ae60", "Compute 8 technical\nindicators per ticker"),
    ("ML\nModel",         "#e67e22", "Score each ticker;\noutput buy probability"),
    ("Signal\nGeneration","#9b59b6", "Emit BUY signals\nwhen confidence >= 0.55"),
    ("Re-evaluation",     "#1abc9c", "Check open signals\n3x/day intraday"),
    ("Outcome\nTracking", "#e74c3c", "Close at day 10;\nrecord win/loss/neutral"),
    ("Backtesting",       "#2c3e50", "Replay model on\nhistorical data"),
]

n = len(steps)
box_w = 1.0
gap = 0.45
box_h = 0.5

shapes = []
annotations = []

for i, (name, color, desc) in enumerate(steps):
    x0 = i * (box_w + gap)
    x1 = x0 + box_w
    y0, y1 = 0.0, box_h

    shapes.append(dict(
        type="rect",
        x0=x0, y0=y0, x1=x1, y1=y1,
        fillcolor=color,
        line=dict(width=0),
        layer="below",
    ))

    # Label inside box
    annotations.append(dict(
        x=(x0 + x1) / 2,
        y=(y0 + y1) / 2,
        text=name.replace("\n", "<br>"),
        showarrow=False,
        font=dict(color="white", size=11, family="Arial"),
        xref="x", yref="y",
        align="center",
    ))

    # Description below box
    annotations.append(dict(
        x=(x0 + x1) / 2,
        y=-0.15,
        text=desc.replace("\n", "<br>"),
        showarrow=False,
        font=dict(color="#555", size=9.5),
        xref="x", yref="y",
        align="center",
    ))

    # Arrow to next box
    if i < n - 1:
        arrow_x = x1 + gap
        annotations.append(dict(
            x=arrow_x, y=(y0 + y1) / 2,
            ax=x1, ay=(y0 + y1) / 2,
            xref="x", yref="y",
            axref="x", ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowwidth=2,
            arrowcolor="#aaa",
        ))

total_width = n * box_w + (n - 1) * gap

fig = go.Figure()
fig.add_trace(go.Scatter(x=[], y=[], mode="markers", showlegend=False))
fig.update_layout(
    shapes=shapes,
    annotations=annotations,
    xaxis=dict(range=[-0.3, total_width + 0.3], showgrid=False, showticklabels=False, zeroline=False),
    yaxis=dict(range=[-0.65, 0.85], showgrid=False, showticklabels=False, zeroline=False),
    plot_bgcolor="white",
    paper_bgcolor="white",
    height=200,
    margin=dict(l=10, r=10, t=10, b=10),
)

st.plotly_chart(fig, width='stretch')

# --- System Domains (single-column) ---
st.subheader("System Domains")

st.markdown("**Data**")
st.markdown("""
Yahoo Finance is the primary data source. Daily OHLCV bars (open, high, low, close,
volume) are fetched for 150 tickers from the Russell 2000 small-cap index ($300M–$2B
market cap) and stored in a SQLite database. The ingestion layer is designed so the
data provider can be swapped (e.g. Polygon.io, Tiingo) with minimal friction.
""")

st.markdown("**ML Model**")
st.markdown("""
A logistic regression classifier serves as the intentionally minimal baseline. It
ingests technical features derived from OHLCV data and outputs a probability that
the stock will be at least 3% higher 10 trading days from now. The model is versioned
and reproducible — complexity is added only after the baseline is validated.
""")

st.markdown("**Signals**")
st.markdown("""
A buy signal is generated whenever the model's confidence score meets or exceeds 0.55.
Each signal carries an entry price (last close), a 5% upside target, a 3% downside
stop-loss, an expected hold time of 10 trading days, and the model version that
produced it.
""")

st.markdown("**Backtesting**")
st.markdown("""
The backtesting layer replays the model over historical OHLCV data, simulates every
signal it would have generated, and resolves each one using the actual close price
10 trading days later. Outcomes are classified win/loss/neutral based on whether the
return exceeded +/-3%. This bootstraps performance metrics before live signals accumulate.
""")

st.markdown("**Pipeline**")
st.markdown("""
Four Prefect flows run on a Monday-Friday schedule. Data ingestion fires at market
open, signal generation runs at 9:30 AM ET, intraday re-evaluation checks open
positions at 11 AM / 1 PM / 3 PM ET, and a closing flow scores outcomes at 4:30 PM ET.
The pipeline is designed to run unattended -- no human intervention is needed during
the trading day.
""")

# --- End-to-End Flow ---
st.subheader("End-to-End Flow")

st.markdown("""
Each trading day begins with a data pull that refreshes up to two years of OHLCV
history for every ticker in the universe. Feature engineering runs on the latest
data to produce the model inputs. The model scores each ticker and emits buy signals
for any that clear the confidence threshold, recording entry, target, stop-loss, and
expected hold time in the database.

Throughout the day, the re-evaluation loop checks every open signal whose hold period
has elapsed. When a signal matures, the current price is compared to the entry price
and the position is closed as a win, loss, or neutral. At market close, a final pass
scores all newly closed signals, updates aggregate metrics, and writes a fresh backtest
summary that will be reflected in the dashboard the next morning.

This loop runs continuously without manual intervention. The only human touchpoint is
reviewing the dashboard to understand how the system is performing and deciding when
to retrain the model.
""")
