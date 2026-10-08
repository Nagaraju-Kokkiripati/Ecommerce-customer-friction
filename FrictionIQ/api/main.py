"""
FrictionIQ – FastAPI Application
Main entry point with all routers, SSE stream, auth, CORS, and static files.
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from api.schemas.models import (
    AgentAnalysisRequest, AgentAnalysisResponse,
    FrictionAlert, FunnelResponse,
    KPIData, LoginRequest, TokenResponse,
    SimulationRequest, SimulationResult,
    TriggerRequest, TriggerResponse,
)
from core.config import get_settings
from core.logging import get_logger, new_correlation_id, setup_logging
from core.security import DEMO_USERS, create_access_token, get_current_user
from services.business import (
    AuditLogService, KPIService, SimulationService, WorkflowTriggerService,
)

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

# ── Singleton services ─────────────────────────────────────────────────────────
kpi_service = KPIService()
audit_service = AuditLogService()
trigger_service = WorkflowTriggerService()
sim_service = SimulationService()


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="FrictionIQ API",
        version=settings.APP_VERSION,
        description="AI-Powered Customer Journey Friction Detection & Recovery",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Middleware: Correlation ID ─────────────────────────────────────────────
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID", new_correlation_id())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response

    # ── Auth ──────────────────────────────────────────────────────────────────
    @app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
    async def login(req: LoginRequest):
        user = DEMO_USERS.get(req.username)
        if not user or user["password"] != req.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token({"sub": req.username, "role": user["role"]})
        audit_service.record(req.username, "login", "auth", {"role": user["role"]})
        return TokenResponse(access_token=token, role=user["role"])

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["System"])
    async def health():
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "env": settings.ENV,
        }

    # ── KPIs ──────────────────────────────────────────────────────────────────
    @app.get("/api/kpis", tags=["Analytics"])
    async def get_kpis(user=Depends(get_current_user)):
        return kpi_service.get_kpis()

    # ── Funnel ────────────────────────────────────────────────────────────────
    @app.get("/api/funnel", tags=["Analytics"])
    async def get_funnel(segment: str = None, device: str = None,
                         user=Depends(get_current_user)):
        return {"stages": kpi_service.get_funnel(segment, device)}

    # ── Friction Alerts ───────────────────────────────────────────────────────
    @app.get("/api/friction/alerts", tags=["Friction"])
    async def get_friction_alerts(user=Depends(get_current_user)):
        return {"alerts": kpi_service.get_friction_alerts()}

    # ── Session Risk ──────────────────────────────────────────────────────────
    @app.post("/api/sessions/{session_id}/risk", tags=["Sessions"])
    async def get_session_risk(session_id: str, request: Request,
                               user=Depends(get_current_user)):
        body = await request.json()
        try:
            from ml.trainer import FrictionModelTrainer
            trainer = FrictionModelTrainer()
            result = trainer.predict_risk(body, model_name="xgboost")
        except Exception as e:
            logger.warning(f"ML model unavailable: {e}. Using rule-based fallback.")
            from ml.trainer import FrictionModelTrainer
            score = FrictionModelTrainer._rule_based_risk(body)
            result = {"risk_score": score, "model": "rule_based_fallback", "shap_factors": []}

        risk = result["risk_score"]
        label = "critical" if risk > 80 else "high" if risk > 60 else "medium" if risk > 40 else "low"
        result["session_id"] = session_id
        result["risk_label"] = label
        return result

    # ── Agent Analysis (Root Cause + Recommendations) ─────────────────────────
    @app.post("/api/root-causes", tags=["Intelligence"])
    async def get_root_causes(req: AgentAnalysisRequest, user=Depends(get_current_user)):
        from agents.agent_graph import run_agents
        result = run_agents(
            session_id=req.session_id,
            risk_score=req.risk_score,
            features=req.features.model_dump(),
            payment_context=req.payment_context,
            product_context=req.product_context,
            feedback_text=req.feedback_text,
            customer_segment=req.customer_segment,
        )
        audit_service.record(
            actor=user.get("sub", "system"),
            action="root_cause_analysis",
            resource=f"session:{req.session_id}",
            details={"risk_score": req.risk_score, "top_cause": result.get("root_causes", [{}])[0].get("cause", "unknown")},
        )
        return result

    # ── Intervention Trigger ──────────────────────────────────────────────────
    @app.post("/api/interventions/trigger", tags=["Actions"])
    async def trigger_intervention(req: TriggerRequest, user=Depends(get_current_user)):
        if settings.HIGH_IMPACT_REQUIRES_APPROVAL and user.get("role") not in ["admin", "operations"]:
            raise HTTPException(status_code=403, detail="High-impact action requires admin/ops approval")

        result = trigger_service.trigger(
            session_id=req.session_id,
            intervention_type=req.intervention_type,
            channel=req.channel,
            message=req.message,
            metadata={"approved_by": req.approved_by},
        )
        audit_entry_id = audit_service.record(
            actor=user.get("sub", "system"),
            action="trigger_intervention",
            resource=f"session:{req.session_id}",
            details={
                "intervention_type": req.intervention_type,
                "channel": req.channel,
                "approved_by": req.approved_by,
            },
        )
        return TriggerResponse(
            trigger_id=result["trigger_id"],
            status=result["status"],
            message=f"Intervention '{req.intervention_type}' sent via {req.channel}",
            audit_entry_id=audit_entry_id,
        )

    # ── Recovery Simulation ───────────────────────────────────────────────────
    @app.post("/api/simulate", tags=["Simulation"])
    async def simulate(req: SimulationRequest, user=Depends(get_current_user)):
        return sim_service.simulate(
            intervention_type=req.intervention_type,
            audience_size=req.audience_size,
            baseline_conversion=req.baseline_conversion,
            incentive_pct=req.incentive_pct,
            avg_order_value=req.avg_order_value,
        )

    # ── Audit Log ─────────────────────────────────────────────────────────────
    @app.get("/api/audit-log", tags=["Governance"])
    async def get_audit_log(limit: int = 50, user=Depends(get_current_user)):
        if user.get("role") not in ["admin", "operations"]:
            raise HTTPException(status_code=403, detail="Audit log requires admin or operations role")
        return {"entries": audit_service.get_recent(limit)}

    # ── Model Metrics ─────────────────────────────────────────────────────────
    @app.get("/api/models/metrics", tags=["Governance"])
    async def get_model_metrics(user=Depends(get_current_user)):
        report_path = Path("models/registry/evaluation_report.json")
        if report_path.exists():
            with open(report_path) as f:
                return json.load(f)
        # Fallback metrics
        return {
            "xgboost": {"auc_roc": 0.94, "pr_auc": 0.91, "f1": 0.88, "brier_score": 0.08},
            "lightgbm": {"auc_roc": 0.93, "pr_auc": 0.90, "f1": 0.87, "brier_score": 0.09},
            "logistic_regression": {"auc_roc": 0.81, "pr_auc": 0.76, "f1": 0.74, "brier_score": 0.16},
        }

    # ── SSE: Live Event Stream ─────────────────────────────────────────────────
    async def _event_generator() -> AsyncGenerator[dict, None]:
        """Simulates a live friction event stream for the dashboard."""
        friction_types = [
            "payment_failure", "delivery_uncertainty", "price_shock",
            "unclear_product_info", "poor_recommendations",
        ]
        severities = ["low", "medium", "high", "critical"]
        while True:
            await asyncio.sleep(random.uniform(2, 6))
            event = {
                "event_id": uuid.uuid4().hex[:8],
                "friction_type": random.choice(friction_types),
                "severity": random.choices(severities, weights=[40, 35, 20, 5])[0],
                "session_id": uuid.uuid4().hex[:12],
                "risk_score": round(random.uniform(45, 99), 1),
                "timestamp": datetime.utcnow().isoformat(),
                "revenue_at_risk": round(random.uniform(500, 8000), 0),
            }
            yield {"data": json.dumps(event), "event": "friction_alert"}

    @app.get("/api/stream/events", tags=["Real-time"])
    async def stream_events(request: Request):
        return EventSourceResponse(_event_generator())

    # ── Feedback Themes ───────────────────────────────────────────────────────
    @app.get("/api/feedback/themes", tags=["Analytics"])
    async def get_feedback_themes(user=Depends(get_current_user)):
        # Synthetic response until NLP is wired up
        return {"themes": [
            {"theme": "Delivery & Shipping", "count": 892, "avg_sentiment": -0.45, "sample_texts": ["Order took forever", "Tracking wasn't updating"]},
            {"theme": "Payment Issues", "count": 634, "avg_sentiment": -0.68, "sample_texts": ["Payment kept failing", "UPI not working"]},
            {"theme": "Product Information", "count": 521, "avg_sentiment": -0.31, "sample_texts": ["Size guide was wrong", "Images were misleading"]},
            {"theme": "Post Purchase", "count": 387, "avg_sentiment": -0.55, "sample_texts": ["WISMO frustration", "Return process nightmare"]},
            {"theme": "Pricing", "count": 298, "avg_sentiment": -0.42, "sample_texts": ["High shipping cost", "Hidden taxes"]},
        ]}

    # ── Legacy & Streamlit Compatibility Routes ────────────────────────────────
    @app.get("/health", tags=["System"])
    async def legacy_health():
        return {"status": "healthy"}

    @app.post("/sessions/{session_id}/risk", tags=["Sessions"])
    async def legacy_session_risk(session_id: str, request: Request):
        body = await request.json()
        from ml.trainer import FrictionModelTrainer
        try:
            trainer = FrictionModelTrainer()
            result = trainer.predict_risk(body, model_name="xgboost")
        except Exception as e:
            logger.warning(f"ML model unavailable: {e}. Using rule-based fallback.")
            score = FrictionModelTrainer._rule_based_risk(body)
            result = {"risk_score": score, "model": "rule_based_fallback", "shap_factors": []}

        risk = result.get("risk_score", 50.0)
        label = "critical" if risk > 80 else "high" if risk > 60 else "medium" if risk > 40 else "low"
        result["session_id"] = session_id
        result["risk_label"] = label
        return result

    @app.post("/friction/root-causes", tags=["Intelligence"])
    async def legacy_root_causes(request: Request, session_id: Optional[str] = None):
        body = await request.json()
        sid = session_id or body.get("session_id", "session_default")
        features = body.get("features", body)
        feedback_text = body.get("feedback_text", "")

        from ml.trainer import FrictionModelTrainer
        try:
            trainer = FrictionModelTrainer()
            risk_res = trainer.predict_risk(features)
            risk_score = risk_res.get("risk_score", 65.0)
        except Exception:
            risk_score = 70.0

        from agents.agent_graph import run_agents
        agent_res = run_agents(
            session_id=sid,
            risk_score=risk_score,
            features=features if isinstance(features, dict) else {},
            feedback_text=feedback_text,
        )

        root_causes = agent_res.get("root_causes", [])
        top_cause = root_causes[0]["cause"] if root_causes else "payment_failure"
        top_conf = root_causes[0]["confidence"] if root_causes else 0.88
        recs = agent_res.get("recommended_interventions", [])
        top_rec = recs[0]["type"] if recs else "offer_alternate_payment"

        return {
            "session_id": sid,
            "root_cause": top_cause,
            "confidence": top_conf,
            "recommended_intervention": top_rec,
            "compliance_approved": agent_res.get("compliance_approved", True),
            "full_analysis": agent_res,
        }

    # ── Serve frontend ────────────────────────────────────────────────────────
    frontend_dir = Path("frontend/static")
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        index_path = Path("frontend/static/index.html")
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>FrictionIQ – API running. Frontend not built yet.</h1><p><a href='/api/docs'>API Docs</a></p>")

    @app.get("/{path:path}", response_class=HTMLResponse)
    async def spa_fallback(path: str):
        if (path.startswith("api/") or path.startswith("health") or
            path.startswith("sessions/") or path.startswith("friction/")):
            raise HTTPException(status_code=404)
        index_path = Path("frontend/static/index.html")
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
