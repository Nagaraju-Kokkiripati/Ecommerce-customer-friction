"""
FrictionIQ – Anomaly & Spike Detection
Uses Isolation Forest on session-level metrics and a simple CUSUM rule
for detecting sudden payment gateway degradation or ETA spikes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from core.logging import get_logger

logger = get_logger(__name__)


class AnomalyDetector:

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.model: IsolationForest | None = None
        self._feature_cols = [
            "num_payment_fails", "payment_fail_rate", "num_rage_clicks",
            "exited_at_checkout", "duration_sec",
        ]

    def fit(self, df: pd.DataFrame) -> "AnomalyDetector":
        cols = [c for c in self._feature_cols if c in df.columns]
        X = df[cols].fillna(0)
        self.model = IsolationForest(contamination=self.contamination, random_state=42, n_jobs=-1)
        self.model.fit(X)
        logger.info("AnomalyDetector trained.")
        return self

    def score(self, df: pd.DataFrame) -> pd.Series:
        if self.model is None:
            return pd.Series(0.0, index=df.index)
        cols = [c for c in self._feature_cols if c in df.columns]
        X = df[cols].fillna(0)
        # IsolationForest returns -1 for anomalies, 1 for normal
        raw = self.model.score_samples(X)
        # Normalize to 0-1 (higher = more anomalous)
        min_s, max_s = raw.min(), raw.max()
        if max_s == min_s:
            return pd.Series(0.0, index=df.index)
        normalized = 1 - (raw - min_s) / (max_s - min_s)
        return pd.Series(normalized, index=df.index)

    def detect_payment_spikes(self, payment_logs: pd.DataFrame, window: str = "1H") -> pd.DataFrame:
        """
        Time-series CUSUM for payment failure rate per gateway.
        Returns a DataFrame of flagged spike windows.
        """
        if payment_logs.empty:
            return pd.DataFrame()

        payment_logs = payment_logs.copy()
        payment_logs["timestamp"] = pd.to_datetime(payment_logs["timestamp"])
        payment_logs["is_fail"] = (payment_logs["status"] == "failed").astype(int)

        spikes = []
        for gateway, grp in payment_logs.groupby("gateway"):
            ts_series = grp.set_index("timestamp")["is_fail"].resample(window).mean().fillna(0)
            baseline = ts_series.mean()
            sigma = ts_series.std() or 1e-6
            cusum = 0.0
            h = 4 * sigma  # threshold
            for ts_val, val in ts_series.items():
                cusum = max(0, cusum + (val - baseline - sigma / 2))
                if cusum > h:
                    spikes.append({
                        "gateway": gateway,
                        "window_start": ts_val,
                        "fail_rate": val,
                        "cusum": cusum,
                        "baseline": baseline,
                        "severity": "high" if cusum > 2 * h else "medium",
                    })
                    cusum = 0  # reset after spike detected

        return pd.DataFrame(spikes)
