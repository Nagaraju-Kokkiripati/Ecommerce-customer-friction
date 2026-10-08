import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, classification_report
import shap
import joblib
import os

class FrictionModel:
    def __init__(self, model_dir="../data/models"):
        self.model_dir = model_dir
        self.model = None
        self.explainer = None
        self.feature_cols = None
        os.makedirs(self.model_dir, exist_ok=True)

    def train(self, features_path="../data/session_features.csv"):
        print(f"Loading features from {features_path}...")
        df = pd.read_csv(features_path)
        
        # Filter out sessions that don't have a label (just in case)
        df = df.dropna(subset=['is_abandoned'])
        
        # Prepare features
        drop_cols = ['session_id', 'friction_label', 'is_abandoned']
        # Also drop categorical for simplicity or one-hot encode them
        if 'device' in df.columns:
            df = pd.get_dummies(df, columns=['device', 'channel'])
            
        self.feature_cols = [c for c in df.columns if c not in drop_cols]
        
        X = df[self.feature_cols]
        y = df['is_abandoned']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Training XGBoost model...")
        self.model = xgb.XGBClassifier(
            n_estimators=100, 
            learning_rate=0.1, 
            max_depth=4, 
            random_state=42,
            eval_metric="logloss"
        )
        self.model.fit(X_train, y_train)
        
        # Evaluate
        preds = self.model.predict(X_test)
        probs = self.model.predict_proba(X_test)[:, 1]
        
        print("\n--- Model Evaluation ---")
        print(f"AUC: {roc_auc_score(y_test, probs):.4f}")
        print(f"Precision: {precision_score(y_test, preds):.4f}")
        print(f"Recall: {recall_score(y_test, preds):.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, preds))
        
        # Save model & features
        joblib.dump(self.model, f"{self.model_dir}/xgb_model.joblib")
        joblib.dump(self.feature_cols, f"{self.model_dir}/feature_cols.joblib")
        
        # Setup SHAP
        self.explainer = shap.TreeExplainer(self.model)
        
        return self.model
        
    def predict_session_risk(self, session_features_dict):
        if not self.model:
            self.model = joblib.load(f"{self.model_dir}/xgb_model.joblib")
            self.feature_cols = joblib.load(f"{self.model_dir}/feature_cols.joblib")
            self.explainer = shap.TreeExplainer(self.model)
            
        # Ensure all columns exist
        df_pred = pd.DataFrame([session_features_dict])
        for col in self.feature_cols:
            if col not in df_pred.columns:
                df_pred[col] = 0
                
        X = df_pred[self.feature_cols]
        prob = self.model.predict_proba(X)[0, 1]
        
        # SHAP
        shap_vals = self.explainer.shap_values(X)
        
        # Top 3 features pushing risk up
        feature_importance = list(zip(self.feature_cols, shap_vals[0]))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        top_factors = feature_importance[:3]
        
        return {
            "risk_score": float(prob * 100),
            "top_risk_factors": [{"feature": f, "impact": float(imp)} for f, imp in top_factors if imp > 0]
        }

if __name__ == "__main__":
    model = FrictionModel()
    model.train()
