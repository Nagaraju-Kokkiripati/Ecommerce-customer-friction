"""
FrictionIQ – Pydantic v2 API Schemas
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ── KPIs ──────────────────────────────────────────────────────────────────────

class KPIData(BaseModel):
    total_sessions: int
    conversion_rate: float
    abandonment_rate: float
    revenue_at_risk: float
    revenue_recovered: float
    support_ticket_volume: int
    avg_risk_score: float
    friction_spike_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Funnel ────────────────────────────────────────────────────────────────────

class FunnelStage(BaseModel):
    stage: str
    sessions: int
    drop_off: int
    drop_off_rate: float
    revenue_at_risk: float

class FunnelResponse(BaseModel):
    stages: list[FunnelStage]
    period: str
    segment_filter: Optional[str] = None


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionRiskRequest(BaseModel):
    num_events: int = 0
    duration_sec: float = 0
    num_product_views: int = 0
    num_compares: int = 0
    num_cart_adds: int = 0
    num_cart_removes: int = 0
    num_searches: int = 0
    num_payment_attempts: int = 0
    num_payment_fails: int = 0
    num_rage_clicks: int = 0
    num_dead_clicks: int = 0
    reached_checkout: int = 0
    reached_payment: int = 0
    placed_order: int = 0
    exited_at_checkout: int = 0
    payment_fail_rate: float = 0
    pages_visited: int = 0
    has_delivery_check: int = 0
    device_mobile: int = 0
    device_desktop: int = 0
    channel_organic: int = 0
    channel_paid: int = 0
    is_new_customer: int = 0
    search_reformulation_count: int = 0

class SHAPFactor(BaseModel):
    feature: str
    impact: float

class SessionRiskResponse(BaseModel):
    session_id: str
    risk_score: float
    risk_label: str  # low / medium / high / critical
    model: str
    shap_factors: list[SHAPFactor]


# ── Root Causes & Recommendations ─────────────────────────────────────────────

class RootCause(BaseModel):
    cause: str
    confidence: float
    evidence: str
    severity: str

class Intervention(BaseModel):
    type: str
    uplift: float
    cost: float
    channel: str
    for_cause: str

class AgentAnalysisRequest(BaseModel):
    session_id: str
    risk_score: float
    features: SessionRiskRequest
    payment_context: dict[str, Any] = {}
    product_context: dict[str, Any] = {}
    feedback_text: str = ""
    customer_segment: str = "general"

class AgentAnalysisResponse(BaseModel):
    session_id: str
    friction_location: str
    root_causes: list[RootCause]
    recommended_interventions: list[Intervention]
    personalized_message: str
    compliance_approved: bool
    compliance_issues: list[str]
    final_decision: str
    reasoning_trace: list[dict]


# ── Friction Alerts ───────────────────────────────────────────────────────────

class FrictionAlert(BaseModel):
    alert_id: str
    friction_type: str
    severity: str
    session_count: int
    revenue_at_risk: float
    timestamp: datetime
    description: str
    recommended_action: str


# ── Feedback Intelligence ─────────────────────────────────────────────────────

class FeedbackTheme(BaseModel):
    theme: str
    count: int
    avg_sentiment: float
    sample_texts: list[str]


# ── Recovery Simulation ───────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    intervention_type: str
    audience_size: int
    baseline_conversion: float = 0.05
    incentive_pct: float = 0.0
    avg_order_value: float = 1500.0
    channel: str = "email"

class SimulationResult(BaseModel):
    intervention_type: str
    expected_conversions: int
    conversion_lift: float
    revenue_recovered: float
    incentive_cost: float
    net_revenue: float
    roi: float
    confidence_interval_low: float
    confidence_interval_high: float


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    entry_id: str
    timestamp: datetime
    actor: str
    action: str
    resource: str
    details: dict
    outcome: str


# ── Interventions ─────────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    session_id: str
    intervention_type: str
    channel: str
    message: str
    approved_by: str

class TriggerResponse(BaseModel):
    trigger_id: str
    status: str
    message: str
    audit_entry_id: str
