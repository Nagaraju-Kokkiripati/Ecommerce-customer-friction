"""Train a candidate on mature captured outcomes, never fabricate training rows.

Run from FrictionIQ: python -m ml.train_captured [--activate]
Labels are session outcome proxies, not verified customer intentions.
"""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone, timedelta

import joblib
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from xgboost import XGBClassifier

from core.config import get_settings
from ml.trainer import FEATURE_COLS
from services.journey_intelligence import extract_features


def samples(db, cutoff):
    result = []
    for row in db.execute("SELECT id,customer_id,created FROM journeys ORDER BY created"):
        if datetime.fromisoformat(row["created"]) > cutoff:
            continue
        events = [dict(e) | {"details": json.loads(e["details"])} for e in db.execute("SELECT type,timestamp,details FROM events WHERE session_id=? ORDER BY id", (row["id"],))]
        success = next((i for i,e in enumerate(events) if e["type"] == "payment_success"), None)
        quantities = {}
        for e in events:
            if e["type"] in ("add_to_cart", "remove_from_cart"):
                quantities[e["details"]["product_id"]] = e["details"]["quantity"]
        if success is None and (not events or not any(quantities.values()) or datetime.fromisoformat(events[-1]["timestamp"]) > cutoff):
            continue
        # Do not let order outcome, inactivity-derived flags, or post-order events leak into predictors.
        features = extract_features(events[:success] if success is not None else events, abandoned=False)
        result.append({"group": row["customer_id"] or row["id"], "created": row["created"], "features": features, "label": int(success is None)})
    return result


def train(activate=False):
    config = get_settings()
    path = config.DATA_DIR / "storefront.sqlite3"
    if not path.exists():
        raise ValueError("No captured database yet. Collect shopping sessions first.")
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        rows = samples(db, datetime.now(timezone.utc) - timedelta(days=1))
    if len(rows) < 100 or min(sum(r["label"] == label for r in rows) for label in (0, 1)) < 20:
        raise ValueError("Need at least 100 mature sessions and 20 examples of each outcome. No model was trained.")
    groups = list(dict.fromkeys(r["group"] for r in rows))
    test_groups = set(groups[max(1,int(len(groups)*.8)):])
    train_rows = [r for r in rows if r["group"] not in test_groups]
    test_rows = [r for r in rows if r["group"] in test_groups]
    if any(len({r["label"] for r in subset}) < 2 for subset in (train_rows, test_rows)):
        raise ValueError("Both train and holdout groups must contain both outcomes. Collect more diverse data.")
    frame = lambda records: pd.DataFrame([{c:r["features"].get(c,0) for c in FEATURE_COLS} for r in records])
    model = XGBClassifier(n_estimators=150, max_depth=3, learning_rate=.05, random_state=42, n_jobs=2)
    model.fit(frame(train_rows), [r["label"] for r in train_rows])
    probabilities = model.predict_proba(frame(test_rows))[:,1]
    labels = [r["label"] for r in test_rows]
    metrics = {"roc_auc": float(roc_auc_score(labels, probabilities)), "pr_auc": float(average_precision_score(labels, probabilities)), "brier_score": float(brier_score_loss(labels, probabilities)), "holdout_sessions": len(test_rows), "train_sessions": len(train_rows), "split": "disjoint customer groups, newest first-seen groups held out"}
    bundle = {"model": model, "feature_cols": FEATURE_COLS, "version": "xgboost_captured_v1", "training_source": "captured_outcome_proxy", "validation_metrics": metrics, "trained_at": datetime.now(timezone.utc).isoformat()}
    target = config.DATA_DIR / ("model_live.joblib" if activate else "model_candidate.joblib")
    joblib.dump(bundle, target)
    print(json.dumps({"saved": str(target), "metrics": metrics, "labels": "Conversion vs mature cart inactivity; these are outcome proxies."}, indent=2))
    if activate:
        print("Restart the API to load the activated model.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    try:
        train(args.activate)
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
