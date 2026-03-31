"""
Prefect flows for the trading signal pipeline.

Run the smoke-test flow locally:
    python -m pipeline.flows
"""
from prefect import flow, task


@task
def noop() -> None:
    """Placeholder task — replace with real pipeline steps."""
    pass


@flow(name="smoke-test")
def smoke_test_flow() -> None:
    """Minimal flow to confirm Prefect is installed and runnable."""
    noop()


if __name__ == "__main__":
    smoke_test_flow()
