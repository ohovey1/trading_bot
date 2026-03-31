from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

from modeling.features import build_labeled_dataset, FEATURE_COLS


def train(db_path: str = "data/trading.db") -> tuple:
    X, y = build_labeled_dataset(db_path)

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, model.predict(X_train))
    test_acc = accuracy_score(y_test, model.predict(X_test))

    print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    print(f"Train accuracy: {train_acc:.3f}, Test accuracy: {test_acc:.3f}")
    print(classification_report(y_test, model.predict(X_test), zero_division=0))

    return model, train_acc, test_acc
