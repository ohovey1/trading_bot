"""
Local scheduler entry point. Starts the Prefect server and runner so all
four pipeline flows run on their cron schedules.

Usage:
    uv run python -m pipeline.scheduler

Press Ctrl-C to stop.
"""
import os
import subprocess
import sys
import time

# Set the API URL *before* any Prefect import so it takes effect at settings load.
_SERVER_URL = "http://127.0.0.1:4200/api"
os.environ.setdefault("PREFECT_API_URL", _SERVER_URL)

from prefect import serve  # noqa: E402 — must come after env-var setup

from pipeline.flows import (  # noqa: E402
    daily_ingest_flow,
    intraday_reeval_flow,
    market_close_outcomes_flow,
    market_open_signals_flow,
)


def _wait_for_server(timeout: int = 90) -> bool:
    """Poll the Prefect server health endpoint until it responds."""
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{_SERVER_URL}/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    # Start the Prefect server as a background subprocess.
    server = subprocess.Popen(
        [sys.executable, "-m", "prefect", "server", "start", "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("Starting Prefect server…", flush=True)

    if not _wait_for_server():
        server.terminate()
        sys.exit("Prefect server did not become healthy within 90 s.")

    print(f"Prefect server ready at {_SERVER_URL}")
    print("Starting flow runner — Ctrl-C to stop.\n")

    try:
        serve(
            daily_ingest_flow.to_deployment(
                name="daily-ingest",
                cron="0 14 * * 1-5",
            ),
            market_open_signals_flow.to_deployment(
                name="market-open-signals",
                cron="30 14 * * 1-5",
            ),
            intraday_reeval_flow.to_deployment(
                name="intraday-reeval",
                cron="0 16,18,20 * * 1-5",
            ),
            market_close_outcomes_flow.to_deployment(
                name="market-close-outcomes",
                cron="30 21 * * 1-5",
            ),
        )
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
