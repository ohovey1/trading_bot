import datetime

from modeling.features import FEATURE_COLS, FORWARD_DAYS, LABEL_THRESHOLD
from modeling.train import train_model
from models.registry import save_model


def main() -> None:
    print("Training model...")
    pipeline, train_metrics, test_metrics = train_model()

    print(f"\nTrain: n={train_metrics['n']}, accuracy={train_metrics['accuracy']:.4f}, ROC-AUC={train_metrics['roc_auc']:.4f}")
    print(f"Test:  n={test_metrics['n']}, accuracy={test_metrics['accuracy']:.4f}, ROC-AUC={test_metrics['roc_auc']:.4f}")
    print(f"\nTest classification report:\n{test_metrics['classification_report']}")

    metadata = {
        "features": FEATURE_COLS,
        "label_forward_days": FORWARD_DAYS,
        "label_threshold_pct": LABEL_THRESHOLD * 100,
        "train_accuracy": train_metrics["accuracy"],
        "train_roc_auc": train_metrics["roc_auc"],
        "train_n": train_metrics["n"],
        "test_accuracy": test_metrics["accuracy"],
        "test_roc_auc": test_metrics["roc_auc"],
        "test_n": test_metrics["n"],
        "training_date": datetime.datetime.utcnow().isoformat(),
    }
    version = save_model(pipeline, metadata)
    print(f"\nModel saved: {version}")


if __name__ == "__main__":
    main()
