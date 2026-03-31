import datetime

from modeling.features import FEATURE_COLS, FORWARD_DAYS, LABEL_THRESHOLD
from modeling.train import train
from modeling.registry import save_model


def main() -> None:
    model, train_acc, test_acc = train()

    metadata = {
        "features": FEATURE_COLS,
        "label_forward_days": FORWARD_DAYS,
        "label_threshold_pct": LABEL_THRESHOLD * 100,
        "train_accuracy": train_acc,
        "test_accuracy": test_acc,
        "training_date": datetime.datetime.utcnow().isoformat(),
    }
    version = save_model(model, metadata)
    print(f"\nModel saved: {version}")


if __name__ == "__main__":
    main()
