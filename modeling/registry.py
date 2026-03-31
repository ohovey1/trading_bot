import json
import pickle
from datetime import datetime
from pathlib import Path

MODELS_DIR = Path("models")


def save_model(model, metadata: dict) -> str:
    MODELS_DIR.mkdir(exist_ok=True)
    version = datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
    pkl_path = MODELS_DIR / f"model_{version}.pkl"
    json_path = MODELS_DIR / f"model_{version}.json"

    with open(pkl_path, "wb") as f:
        pickle.dump(model, f)

    with open(json_path, "w") as f:
        json.dump({"version": version, **metadata}, f, indent=2, default=str)

    return version


def load_latest_model():
    pkls = sorted(MODELS_DIR.glob("model_v*.pkl"))
    if not pkls:
        raise FileNotFoundError(f"No model artifacts found in {MODELS_DIR}/")
    with open(pkls[-1], "rb") as f:
        return pickle.load(f)
