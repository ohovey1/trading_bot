import json
import pickle
from pathlib import Path

MODELS_DIR = Path("models")


def _next_version() -> int:
    existing = sorted(MODELS_DIR.glob("model_v*.pkl"))
    if not existing:
        return 1
    nums = []
    for p in existing:
        stem = p.stem  # e.g. "model_v3"
        try:
            nums.append(int(stem.split("_v")[1]))
        except (IndexError, ValueError):
            pass
    return max(nums) + 1 if nums else 1


def save_model(pipeline, metadata: dict) -> str:
    """Save pipeline and metadata, auto-incrementing version. Returns version string."""
    MODELS_DIR.mkdir(exist_ok=True)
    n = _next_version()
    version = f"v{n}"
    pkl_path = MODELS_DIR / f"model_{version}.pkl"
    json_path = MODELS_DIR / f"model_{version}.json"

    with open(pkl_path, "wb") as f:
        pickle.dump(pipeline, f)

    with open(json_path, "w") as f:
        json.dump({"version": version, **metadata}, f, indent=2, default=str)

    return version


def load_model(version: str | None = None):
    """Load a model by version (e.g. 'v2'). Loads latest if version is None."""
    if version is not None:
        pkl_path = MODELS_DIR / f"model_{version}.pkl"
        if not pkl_path.exists():
            raise FileNotFoundError(f"Model not found: {pkl_path}")
        with open(pkl_path, "rb") as f:
            return pickle.load(f)

    pkls = sorted(MODELS_DIR.glob("model_v*.pkl"))
    if not pkls:
        raise FileNotFoundError(f"No model artifacts found in {MODELS_DIR}/")
    with open(pkls[-1], "rb") as f:
        return pickle.load(f)
