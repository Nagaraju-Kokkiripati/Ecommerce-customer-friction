"""
FrictionIQ – Services Layer
Wraps ML models and agents into clean business logic.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class AuditLogService:
    """Immutable append-only audit log (in-memory for dev, DB-backed in prod)."""

    def __init__(self):
        self._log: list[dict] = []

    def record(self, actor: str, action: str, resource: str,
               details: dict, outcome: str = "success") -> str:
        entry_id = str(uuid.uuid4())
        entry = {
            "entry_id": entry_id,
            "timestamp": datetime.utcnow().isoformat(),
            "actor": actor,
            "action": action,
            "resource": resource,
            "details": details,
            "outcome": outcome,
        }
        self._log.append(entry)
        logger.info(f"AUDIT: {action} by {actor} on {resource} -> {outcome}")
        return entry_id

    def get_recent(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._log[-limit:]))


class WorkflowTriggerService:
    """Mock webhook/adapter layer for triggering recovery actions."""

    MOCK_LATENCIES_MS = {"email": 120, "sms": 80, "push": 60, "in_app": 30, "chat": 200}

    def trigger(self, session_id: str, intervention_type: str,
                channel: str, message: str, metadata: dict) -> dict:
        import time
        time.sleep(self.MOCK_LATENCIES_MS.get(channel, 100) / 1000)
        trigger_id = f"TRG-{uuid.uuid4().hex[:8].upper()}"
        return {
            "trigger_id": trigger_id,
            "status": "sent",
            "channel": channel,
            "intervention_type": intervention_type,
            "timestamp": datetime.utcnow().isoformat(),
        }


class KPIService:
    """Computes real-time KPIs from feature store and data files."""

    def __init__(self):
        self._feature_path = settings.FEATURE_STORE_DIR / "session_features.parquet"
        self._payments_path = settings.PROCESSED_DIR / "payment_logs.parquet"
        self._tickets_path = settings.PROCESSED_DIR / "support_tickets.parquet"
        self._recovery_path = settings.PROCESSED_DIR / "recovery_responses.parquet"
        self._df: Optional[pd.DataFrame] = None

    def _load(self) -> pd.DataFrame:
        if self._df is None or (datetime.utcnow().minute % 5 == 0):  # refresh every 5 min
            if self._feature_path.exists():
                self._df = pd.read_parquet(self._feature_path)
            else:
                # Return synthetic KPIs if no data available yet
                self._df = pd.DataFrame()
        return self._df

    def get_kpis(self) -> dict:
        df = self._load()
        if df.empty:
            return self._synthetic_kpis()

        total = len(df)
        abandoned = int(df.get("is_abandoned", pd.Series(dtype=int)).sum()) if "is_abandoned" in df.columns else int(total * 0.72)
        conversion = round((1 - abandoned / total) * 100, 1) if total else 0
        avg_risk = round(df.get("payment_fail_rate", pd.Series(0.0)).mean() * 100, 1)

        # Revenue at risk (rough estimate: avg order ~₹1800 * at-risk sessions)
        revenue_at_risk = round(abandoned * 1800 * 0.15, 0)

        # Recovery data
        revenue_recovered = 0.0
        if self._recovery_path.exists():
            rec = pd.read_parquet(self._recovery_path)
            revenue_recovered = float(rec[rec["converted"]]["revenue_recovered"].sum())

        ticket_volume = 0
        if self._tickets_path.exists():
            tickets = pd.read_parquet(self._tickets_path)
            ticket_volume = len(tickets)

        return {
            "total_sessions": total,
            "conversion_rate": conversion,
            "abandonment_rate": round(abandoned / total * 100, 1) if total else 0,
            "revenue_at_risk": revenue_at_risk,
            "revenue_recovered": round(revenue_recovered, 0),
            "support_ticket_volume": ticket_volume,
            "avg_risk_score": avg_risk,
            "friction_spike_count": random.randint(2, 8),  # placeholder for anomaly service
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_funnel(self, segment: Optional[str] = None,
                   device: Optional[str] = None) -> list[dict]:
        df = self._load()
        if df.empty:
            return self._synthetic_funnel()

        total = len(df)
        stages = [
            ("Browse/Discovery", total, 0),
            ("Product View", int(df.get("num_product_views", pd.Series(dtype=float)).gt(0).sum()), 0),
            ("Add to Cart", int(df.get("num_cart_adds", pd.Series(dtype=float)).gt(0).sum()), 0),
            ("Checkout Start", int(df.get("reached_checkout", pd.Series(0)).sum()), 0),
            ("Payment Attempted", int(df.get("reached_payment", pd.Series(0)).sum()), 0),
            ("Order Placed", int(df.get("placed_order", pd.Series(0)).sum()), 0),
        ]
        result = []
        for i, (stage, count, _) in enumerate(stages):
            prev = stages[i - 1][1] if i > 0 else count
            drop_off = max(0, prev - count)
            result.append({
                "stage": stage,
                "sessions": count,
                "drop_off": drop_off,
                "drop_off_rate": round(drop_off / prev * 100, 1) if prev else 0,
                "revenue_at_risk": round(drop_off * 1800 * 0.12, 0),
            })
        return result

    def get_friction_alerts(self) -> list[dict]:
        """Generates friction alerts from anomaly detections + aggregate signals."""
        alerts = []
        df = self._load()
        if df.empty:
            return self._synthetic_alerts()

        # Payment failure spike
        if "num_payment_fails" in df.columns:
            pf_sessions = int(df["num_payment_fails"].gt(0).sum())
            if pf_sessions > 50:
                alerts.append({
                    "alert_id": str(uuid.uuid4())[:8],
                    "friction_type": "payment_failure",
                    "severity": "high" if pf_sessions > 200 else "medium",
                    "session_count": pf_sessions,
                    "revenue_at_risk": round(pf_sessions * 2200 * 0.40, 0),
                    "timestamp": datetime.utcnow().isoformat(),
                    "description": f"{pf_sessions} sessions experienced payment failures",
                    "recommended_action": "Enable alternate payment method prompt",
                })

        # Rage click anomaly
        if "num_rage_clicks" in df.columns:
            rage_sessions = int(df["num_rage_clicks"].gt(2).sum())
            if rage_sessions > 20:
                alerts.append({
                    "alert_id": str(uuid.uuid4())[:8],
                    "friction_type": "technical_friction",
                    "severity": "medium",
                    "session_count": rage_sessions,
                    "revenue_at_risk": round(rage_sessions * 1500 * 0.25, 0),
                    "timestamp": (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                    "description": f"{rage_sessions} sessions with rage clicks detected",
                    "recommended_action": "Investigate product page UI/UX issues",
                })

        return alerts

    @staticmethod
    def _synthetic_kpis() -> dict:
        return {
            "total_sessions": 10247,
            "conversion_rate": 28.4,
            "abandonment_rate": 71.6,
            "revenue_at_risk": 2_456_800,
            "revenue_recovered": 312_400,
            "support_ticket_volume": 1842,
            "avg_risk_score": 62.3,
            "friction_spike_count": 4,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _synthetic_funnel() -> list[dict]:
        stages = [
            ("Browse/Discovery", 10247, 0),
            ("Product View", 7821, 2426),
            ("Add to Cart", 4312, 3509),
            ("Checkout Start", 3105, 1207),
            ("Payment Attempted", 2234, 871),
            ("Order Placed", 1842, 392),
        ]
        return [
            {
                "stage": s, "sessions": c, "drop_off": d,
                "drop_off_rate": round(d / (c + d) * 100, 1) if d else 0,
                "revenue_at_risk": round(d * 1800 * 0.12, 0),
            }
            for s, c, d in stages
        ]

    @staticmethod
    def _synthetic_alerts() -> list[dict]:
        return [
            {
                "alert_id": "a1b2c3d4",
                "friction_type": "payment_failure",
                "severity": "high",
                "session_count": 342,
                "revenue_at_risk": 615600,
                "timestamp": datetime.utcnow().isoformat(),
                "description": "Payment failure rate spiked to 38% on Razorpay (3DS_TIMEOUT)",
                "recommended_action": "Enable UPI fallback prompt immediately",
            },
            {
                "alert_id": "e5f6g7h8",
                "friction_type": "delivery_uncertainty",
                "severity": "medium",
                "session_count": 189,
                "revenue_at_risk": 198450,
                "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                "description": "189 sessions dropped after ETA check showing >10 days",
                "recommended_action": "Show delivery promise with guaranteed date",
            },
        ]


class SimulationService:
    """Recovery intervention simulator with confidence intervals."""

    UPLIFT_BY_INTERVENTION = {
        "alternate_payment_method": (0.18, 0.28),
        "smart_payment_retry": (0.12, 0.22),
        "delivery_date_promise": (0.15, 0.25),
        "targeted_incentive_5pct": (0.08, 0.15),
        "targeted_incentive_10pct": (0.12, 0.22),
        "targeted_incentive_15pct": (0.16, 0.28),
        "cart_reminder": (0.06, 0.12),
        "clarify_product_info": (0.10, 0.18),
        "proactive_delay_notification": (0.20, 0.35),
        "support_escalation": (0.05, 0.15),
        "recommendation_rerank": (0.06, 0.14),
    }

    def simulate(self, intervention_type: str, audience_size: int,
                 baseline_conversion: float = 0.05, incentive_pct: float = 0.0,
                 avg_order_value: float = 1500.0) -> dict:
        uplift_range = self.UPLIFT_BY_INTERVENTION.get(intervention_type, (0.05, 0.15))
        uplift_mean = (uplift_range[0] + uplift_range[1]) / 2
        uplift_std = (uplift_range[1] - uplift_range[0]) / 4

        import numpy as np
        samples = np.random.normal(uplift_mean, uplift_std, 1000)
        samples = np.clip(samples, 0, 0.8)

        expected_uplift = float(np.mean(samples))
        ci_low = float(np.percentile(samples, 5))
        ci_high = float(np.percentile(samples, 95))

        new_conversion = baseline_conversion + expected_uplift * (1 - baseline_conversion)
        expected_conversions = int(audience_size * new_conversion)
        revenue_recovered = round(expected_conversions * avg_order_value, 0)
        incentive_cost = round(revenue_recovered * (incentive_pct / 100), 0)
        net_revenue = revenue_recovered - incentive_cost
        roi = round(net_revenue / max(incentive_cost, 1) * 100, 1)

        return {
            "intervention_type": intervention_type,
            "expected_conversions": expected_conversions,
            "conversion_lift": round(expected_uplift * 100, 1),
            "revenue_recovered": revenue_recovered,
            "incentive_cost": incentive_cost,
            "net_revenue": net_revenue,
            "roi": roi,
            "confidence_interval_low": round(ci_low * 100, 1),
            "confidence_interval_high": round(ci_high * 100, 1),
        }
