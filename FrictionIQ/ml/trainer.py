"""
FrictionIQ – ML Model Registry & Trainer
Trains multiple models, evaluates them, and saves the best to the registry.

Models:
  1. Logistic Regression (baseline)
  2. LightGBM
  3. XGBoost
  4. CatBoost (if installed, else skips gracefully)
  Compares on AUC-ROC, PR-AUC, F1, Brier score.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
    classification_report,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import catboost as cb
    HAS_CB = True
except ImportError:
    HAS_CB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

from core.logging import get_logger

warnings.filterwarnings("ignore")
logger = get_logger(__name__)

# Features used for training (no PII, no ground truth)
FEATURE_COLS = [
    "num_events", "duration_sec", "num_product_views", "num_compares",
    "num_cart_adds", "num_cart_removes", "num_searches",
    "num_payment_attempts", "num_payment_fails", "num_rage_clicks",
    "num_dead_clicks", "reached_checkout", "reached_payment",
    "exited_at_checkout", "payment_fail_rate", "pages_visited",
    "has_delivery_check", "device_mobile", "device_desktop",
    "channel_organic", "channel_paid", "is_new_customer",
    "search_reformulation_count",
]
TARGET_COL = "is_abandoned"


class ModelRegistry:
    """Saves, loads, and compares trained models with metadata."""

    def __init__(self, registry_dir: str = "models/registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.registry_dir / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        if self._index_path.exists():
            with open(self._index_path) as f:
                self._index: dict[str, Any] = json.load(f)
        else:
            self._index = {}

    def _save_index(self) -> None:
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2, default=str)

    def save(self, name: str, model: Any, metrics: dict, feature_cols: list[str],
             scaler: Optional[Any] = None, explainer: Optional[Any] = None) -> Path:
        version = len([k for k in self._index if k.startswith(name)]) + 1
        key = f"{name}_v{version}"
        model_path = self.registry_dir / f"{key}.joblib"
        joblib.dump({"model": model, "scaler": scaler, "feature_cols": feature_cols}, model_path)
        if explainer is not None:
            exp_path = self.registry_dir / f"{key}_explainer.joblib"
            joblib.dump(explainer, exp_path)
        self._index[key] = {
            "name": name,
            "version": version,
            "path": str(model_path),
            "metrics": metrics,
            "feature_cols": feature_cols,
        }
        self._save_index()
        logger.info(f"Model saved: {key}  AUC={metrics.get('auc_roc', 0):.4f}")
        return model_path

    def load_best(self, name: str) -> Optional[dict[str, Any]]:
        candidates = {k: v for k, v in self._index.items() if v["name"] == name}
        if not candidates:
            return None
        best_key = max(candidates, key=lambda k: candidates[k]["metrics"].get("auc_roc", 0))
        return joblib.load(candidates[best_key]["path"])

    def get_metrics_report(self) -> list[dict]:
        return [{"key": k, **v} for k, v in self._index.items()]


def _evaluate(model: Any, X_test: pd.DataFrame, y_test: pd.Series,
              scaler: Optional[Any] = None) -> dict:
    if scaler:
        X_test = scaler.transform(X_test)
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs > 0.5).astype(int)
    return {
        "auc_roc": float(roc_auc_score(y_test, probs)),
        "pr_auc": float(average_precision_score(y_test, probs)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "brier_score": float(brier_score_loss(y_test, probs)),
        "support_positive": int(y_test.sum()),
        "support_total": int(len(y_test)),
    }


class FrictionModelTrainer:

    def __init__(
        self,
        feature_store_dir: str = "data/feature_store",
        registry_dir: str = "models/registry",
    ):
        self.feature_store = Path(feature_store_dir)
        self.registry = ModelRegistry(registry_dir)

    def _load_features(self) -> tuple[pd.DataFrame, pd.Series]:
        path = self.feature_store / "session_features.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Feature store not found: {path}. Run feature engineering first.")
        df = pd.read_parquet(path)
        df = df.dropna(subset=[TARGET_COL])

        available = [c for c in FEATURE_COLS if c in df.columns]
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        if missing:
            logger.warning(f"Missing feature columns (will use 0): {missing}")
            for c in missing:
                df[c] = 0

        X = df[FEATURE_COLS].fillna(0)
        y = df[TARGET_COL].astype(int)
        return X, y

    def train_all(self) -> dict[str, dict]:
        X, y = self._load_features()
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        results: dict[str, dict] = {}

        # ── 1. Logistic Regression (baseline) ────────────────────────────────
        logger.info("Training LogisticRegression baseline...")
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_train)
        lr = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
        lr.fit(X_tr_scaled, y_train)
        metrics = _evaluate(lr, X_test, y_test, scaler)
        self.registry.save("logistic_regression", lr, metrics, FEATURE_COLS, scaler=scaler)
        results["logistic_regression"] = metrics
        print(f"  LR    AUC={metrics['auc_roc']:.4f}  F1={metrics['f1']:.4f}")

        # ── 2. LightGBM ───────────────────────────────────────────────────────
        if HAS_LGB:
            logger.info("Training LightGBM...")
            lgb_model = lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=6,
                num_leaves=63, random_state=42, n_jobs=-1,
                class_weight="balanced", verbose=-1,
            )
            lgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
            metrics = _evaluate(lgb_model, X_test, y_test)
            explainer = None
            if HAS_SHAP:
                explainer = shap.TreeExplainer(lgb_model)
            self.registry.save("lightgbm", lgb_model, metrics, FEATURE_COLS, explainer=explainer)
            results["lightgbm"] = metrics
            print(f"  LGB   AUC={metrics['auc_roc']:.4f}  F1={metrics['f1']:.4f}")
        else:
            logger.warning("LightGBM not installed – skipping.")

        # ── 3. XGBoost ────────────────────────────────────────────────────────
        if HAS_XGB:
            logger.info("Training XGBoost...")
            xgb_model = xgb.XGBClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=6,
                random_state=42, n_jobs=-1, eval_metric="logloss",
                scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
            )
            xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            metrics = _evaluate(xgb_model, X_test, y_test)
            explainer = None
            if HAS_SHAP:
                explainer = shap.TreeExplainer(xgb_model)
            self.registry.save("xgboost", xgb_model, metrics, FEATURE_COLS, explainer=explainer)
            results["xgboost"] = metrics
            print(f"  XGB   AUC={metrics['auc_roc']:.4f}  F1={metrics['f1']:.4f}")
        else:
            logger.warning("XGBoost not installed – skipping.")

        # ── 4. CatBoost ───────────────────────────────────────────────────────
        if HAS_CB:
            logger.info("Training CatBoost...")
            cb_model = cb.CatBoostClassifier(
                iterations=300, learning_rate=0.05, depth=6,
                random_seed=42, verbose=0, auto_class_weights="Balanced",
            )
            cb_model.fit(X_train, y_train, eval_set=(X_test, y_test))
            metrics = _evaluate(cb_model, X_test, y_test)
            self.registry.save("catboost", cb_model, metrics, FEATURE_COLS)
            results["catboost"] = metrics
            print(f"  CB    AUC={metrics['auc_roc']:.4f}  F1={metrics['f1']:.4f}")
        else:
            logger.warning("CatBoost not installed – skipping.")

        # Print comparison table
        print("\n" + "=" * 60)
        print("Model Comparison:")
        print(f"{'Model':<22} {'AUC-ROC':>8} {'PR-AUC':>8} {'F1':>8} {'Brier':>8}")
        print("-" * 60)
        for model_name, m in results.items():
            print(f"{model_name:<22} {m['auc_roc']:>8.4f} {m['pr_auc']:>8.4f} {m['f1']:>8.4f} {m['brier_score']:>8.4f}")

        # Save full report
        report_path = Path("models/registry") / "evaluation_report.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nEvaluation report saved → {report_path}")

        return results

    def predict_risk(self, session_features: dict[str, Any], model_name: str = "xgboost") -> dict:
        """
        Real-time risk scoring for a single session.
        Returns: risk_score (0-100), top SHAP factors, and fallback if model missing.
        """
        bundle = self.registry.load_best(model_name)
        if bundle is None:
            # Rule-based fallback
            score = self._rule_based_risk(session_features)
            return {"risk_score": score, "model": "rule_based_fallback", "shap_factors": []}

        model = bundle["model"]
        scaler = bundle.get("scaler")
        feature_cols = bundle.get("feature_cols", FEATURE_COLS)

        df = pd.DataFrame([session_features])
        for c in feature_cols:
            if c not in df.columns:
                df[c] = 0
        X = df[feature_cols].fillna(0)

        if scaler:
            X_val = scaler.transform(X)
        else:
            X_val = X.values

        prob = model.predict_proba(X_val)[0, 1]

        # SHAP explanation
        shap_factors = []
        if HAS_SHAP:
            try:
                exp_path = Path("models/registry")
                # Find explainer for this model
                explainer_key = [k for k in self.registry._index if k.startswith(model_name) and "explainer" in k]
                if not explainer_key:
                    # Try to build inline
                    explainer = shap.TreeExplainer(model)
                else:
                    explainer = joblib.load(Path("models/registry") / f"{explainer_key[0]}.joblib")
                shap_vals = explainer.shap_values(pd.DataFrame([session_features])[feature_cols].fillna(0))
                if isinstance(shap_vals, list):
                    shap_vals = shap_vals[1]  # positive class
                pairs = sorted(zip(feature_cols, shap_vals[0]), key=lambda x: abs(x[1]), reverse=True)
                shap_factors = [{"feature": f, "impact": round(float(v), 4)} for f, v in pairs[:5]]
            except Exception as e:
                logger.warning(f"SHAP failed: {e}")

        return {
            "risk_score": round(float(prob) * 100, 1),
            "model": model_name,
            "shap_factors": shap_factors,
        }

    @staticmethod
    def _rule_based_risk(features: dict) -> float:
        """Fallback risk scoring using business rules."""
        score = 20.0
        if features.get("num_payment_fails", 0) > 0:
            score += 40
        if features.get("exited_at_checkout", 0):
            score += 25
        if features.get("payment_fail_rate", 0) > 0.5:
            score += 15
        if features.get("num_compares", 0) > 3:
            score += 10
        if features.get("num_rage_clicks", 0) > 2:
            score += 15
        return min(score, 100.0)


if __name__ == "__main__":
    trainer = FrictionModelTrainer()
    trainer.train_all()
