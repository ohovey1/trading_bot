"""
Standalone Yahoo Finance diagnostic — no project dependencies.

Usage:
    uv run python data/diagnostics/yf_diagnostic.py

Checks AAPL, MSFT, SPY: measures wall-clock time, prints response shape,
catches exceptions, and prints a final pass/fail summary.
"""

import time
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "SPY"]
TIMEOUT = 15  # seconds per ticker

results = {}
script_start = time.perf_counter()

for ticker in TICKERS:
    print(f"\n[{ticker}] Fetching 5d/1d data...")
    t0 = time.perf_counter()
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False, timeout=TIMEOUT)
        elapsed = time.perf_counter() - t0
        shape = f"{df.shape[0]}r x {df.shape[1]}c"
        print(f"[{ticker}] OK — {shape} in {elapsed:.2f}s")
        results[ticker] = ("PASS", elapsed, shape)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"[{ticker}] FAIL — {type(e).__name__}: {e} ({elapsed:.2f}s)")
        results[ticker] = ("FAIL", elapsed, str(e))

total_elapsed = time.perf_counter() - script_start

print("\n" + "=" * 50)
print(f"SUMMARY  total={total_elapsed:.2f}s")
print("=" * 50)
for ticker, (status, elapsed, detail) in results.items():
    print(f"  {ticker:<6} {status}  {elapsed:.2f}s  {detail}")
print("=" * 50)
