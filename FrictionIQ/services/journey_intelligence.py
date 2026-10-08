"""Predict from captured features; never manufacture model accuracy metrics."""
from functools import lru_cache
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parents[1] / "models/registry/xgboost_v1.joblib"


@lru_cache(maxsize=1)
def load_model():
    import joblib
    from core.config import get_settings
    live_path = get_settings().DATA_DIR / "model_live.joblib"
    return joblib.load(live_path if live_path.exists() else MODEL_PATH)


def extract_features(events, abandoned=False):
    counts = {}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    from datetime import datetime
    duration = (datetime.fromisoformat(events[-1]["timestamp"]) - datetime.fromisoformat(events[0]["timestamp"])).total_seconds() if events else 0
    failures, attempts = counts.get("payment_failure", 0), counts.get("payment_attempt", 0)
    features = {
        "num_events": len(events), "duration_sec": duration,
        "num_product_views": counts.get("product_view", 0), "num_compares": counts.get("product_compare", 0),
        "num_cart_adds": counts.get("add_to_cart", 0), "num_cart_removes": counts.get("remove_from_cart", 0),
        "num_searches": counts.get("search", 0), "num_payment_attempts": attempts,
        "num_payment_fails": failures, "reached_checkout": int(bool(counts.get("checkout_start"))),
        "reached_payment": int(bool(attempts)), "exited_at_checkout": int(abandoned and bool(counts.get("checkout_start"))),
        "payment_fail_rate": failures / attempts if attempts else 0,
        "pages_visited": len({e["type"] for e in events}),
        "search_reformulation_count": max(0, counts.get("search", 0) - 1),
        "device_mobile": counts.get("device_mobile", 0) > 0,
        "device_desktop": counts.get("device_desktop", 0) > 0,
    }
    return features


def predict(events, abandoned=False):
    features = extract_features(events, abandoned)
    try:
        import pandas as pd
        bundle = load_model()
        frame = pd.DataFrame([{c: features.get(c, 0) for c in bundle["feature_cols"]}])
        score = round(float(bundle["model"].predict_proba(frame)[0, 1]) * 100, 1)
        # XGBoost's native TreeSHAP contributions need no saved explainer pickle.
        import xgboost as xgb
        values = bundle["model"].get_booster().predict(xgb.DMatrix(frame), pred_contribs=True)[0]
        drivers = sorted(zip(bundle["feature_cols"], values[:-1]), key=lambda pair: abs(pair[1]), reverse=True)[:5]
        return {"model": bundle.get("version", "xgboost_v1"), "risk_score": score, "drivers": [{"feature": f, "impact": round(float(v), 4)} for f, v in drivers], "training_source": bundle.get("training_source", "synthetic"), "features": features, "limitation": "Live accuracy is not validated. Uncaptured features use zero."}
    except Exception as error:
        logger.warning("Model prediction unavailable: %s", error)
        return {"model": "unavailable", "risk_score": None, "drivers": [], "features": features, "limitation": "Use observed-event rules until the model dependencies are available."}
