"""Live storefront API. Analytics are derived exclusively from captured events."""
import hmac
import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.shop import admin, database, journey_detail, password_hash, router
from core.config import get_settings
from core.security import create_access_token
from services.journey_intelligence import load_model

attempts = defaultdict(list)


class Credentials(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=128)


def snapshot(db):
    sessions = db.execute("SELECT id,customer_id FROM journeys").fetchall()
    by_session = {}
    for row in db.execute("SELECT session_id,type,timestamp,details FROM events ORDER BY id"):
        by_session.setdefault(row["session_id"], []).append(dict(row))
    from datetime import datetime, timezone
    threshold = get_settings().ABANDONMENT_MINUTES * 60
    abandoned, converted, failures, at_risk = 0, 0, 0, 0
    funnel = [0] * 6
    for s in sessions:
        events = by_session.get(s["id"], [])
        kinds = {e["type"] for e in events}
        completed = "order_placed" in kinds
        converted += completed
        failures += sum(e["type"] == "payment_failure" for e in events)
        inactive = (datetime.now(timezone.utc) - datetime.fromisoformat(events[-1]["timestamp"])).total_seconds() if events else 0
        latest_quantities = {}
        for e in events:
            if e["type"] in ("add_to_cart", "remove_from_cart"):
                detail = json.loads(e["details"])
                latest_quantities[detail["product_id"]] = detail["quantity"]
        abandoned += not completed and any(latest_quantities.values()) and inactive >= threshold
        for i, flag in enumerate([True, "product_view" in kinds, "add_to_cart" in kinds, "checkout_start" in kinds, "payment_attempt" in kinds, completed]):
            funnel[i] += flag
        if not completed and "payment_failure" in kinds:
            totals = [json.loads(e["details"]).get("total", 0) for e in events if e["type"] == "payment_failure"]
            at_risk += max(totals, default=0)
    order_total = db.execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]
    recovery_revenue = db.execute("SELECT COALESCE(SUM(o.total),0) FROM orders o WHERE EXISTS (SELECT 1 FROM recoveries r JOIN journeys j ON j.id=r.session_id WHERE j.customer_id=o.customer_id AND r.created<o.created AND r.status IN ('accepted','simulated'))").fetchone()[0]
    count = len(sessions)
    return {"total_sessions": count, "converted_sessions": converted, "conversion_rate": round(converted / count * 100, 1) if count else 0, "abandonment_rate": round(abandoned / count * 100, 1) if count else 0, "possibly_abandoned_sessions": abandoned, "payment_failures": failures, "revenue_at_risk": at_risk, "revenue_recovered": recovery_revenue, "order_revenue": order_total, "source": "captured_events", "funnel": [{"stage": name, "sessions": value} for name, value in zip(["Sessions", "Product view", "Cart", "Checkout", "Payment", "Order"], funnel)]}


def create_app():
    config = get_settings()
    app = FastAPI(title="FrictionIQ", docs_url="/api/docs")
    app.include_router(router)
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type", "Authorization"])

    @app.middleware("http")
    async def response_security(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in ("POST", "PUT", "DELETE") and origin and origin not in config.ALLOWED_ORIGINS and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin action denied"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path != "/api/docs":
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/auth/login")
    def login(body: Credentials, request: Request):
        key = (request.client.host if request.client else "unknown", body.username)
        recent = [t for t in attempts[key] if time.monotonic() - t < 300]
        attempts[key] = recent
        if len(recent) >= 10:
            raise HTTPException(429, "Too many attempts; retry in five minutes")
        recent.append(time.monotonic())
        valid = False
        if body.username == config.ADMIN_USERNAME:
            if config.ADMIN_PASSWORD_HASH:
                salt = config.ADMIN_PASSWORD_HASH.split(":")[0]
                valid = hmac.compare_digest(password_hash(body.password, salt), config.ADMIN_PASSWORD_HASH)
            elif config.ENV == "development":
                valid = hmac.compare_digest(body.password, "admin123")
        if not valid:
            raise HTTPException(401, "Invalid credentials")
        attempts.pop(key, None)
        return {"access_token": create_access_token({"sub": body.username, "role": "admin"}), "role": "admin", "token_type": "bearer"}

    @app.get("/api/health")
    @app.get("/health")
    def health():
        return {"status": "healthy", "version": config.APP_VERSION}

    @app.get("/api/kpis", dependencies=[Depends(admin)])
    def kpis(db=Depends(database)):
        return snapshot(db)

    @app.get("/api/funnel", dependencies=[Depends(admin)])
    def funnel(db=Depends(database)):
        return {"stages": snapshot(db)["funnel"], "source": "captured_events"}

    @app.get("/api/friction/alerts", dependencies=[Depends(admin)])
    def alerts(db=Depends(database)):
        result = []
        for row in db.execute("SELECT DISTINCT session_id FROM events WHERE type IN ('payment_failure','search_no_results') ORDER BY id DESC LIMIT 100").fetchall():
            item = journey_detail(db, row[0])
            if not item["completed"]:
                result.append({"session_id": item["session_id"], "risk_score": item["risk_score"], "facts": item["facts"], "recommended_action": item["recommendation"]})
        return {"alerts": result, "source": "captured_events"}

    @app.get("/api/models/metrics", dependencies=[Depends(admin)])
    def model():
        try:
            bundle = load_model()
            available = True
        except Exception:
            available = False
        return {"model": bundle.get("version", "xgboost_v1") if available else "unavailable", "available": available, "training_source": bundle.get("training_source", "synthetic") if available else None, "offline_validation_metrics": bundle.get("validation_metrics") if available else None, "live_validation_metrics": None, "llm": "none", "email_mode": config.EMAIL_MODE}

    @app.get("/api/audit-log", dependencies=[Depends(admin)])
    def audit(db=Depends(database)):
        return {"entries": [dict(r) for r in db.execute("SELECT id,session_id,channel,created,status,error FROM recoveries ORDER BY created DESC LIMIT 100")]}

    @app.get("/api/feedback/themes", dependencies=[Depends(admin)])
    def feedback():
        return {"themes": [], "message": "No customer feedback collected yet"}

    @app.post("/api/sessions/{sid}/risk", dependencies=[Depends(admin)])
    def session_risk(sid: str, db=Depends(database)):
        item = journey_detail(db, sid)
        return {"session_id": sid, "observed_rule_score": item["risk_score"], **item["prediction"]}

    @app.post("/api/root-causes", dependencies=[Depends(admin)])
    async def causes(request: Request, db=Depends(database)):
        body = await request.json()
        return journey_detail(db, body.get("session_id", ""))

    directory = Path(__file__).resolve().parents[1] / "frontend/static"
    app.mount("/static", StaticFiles(directory=directory), name="static")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/admin", response_class=HTMLResponse)
    @app.get("/admin/journeys", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse((directory / "journeys.html").read_text(encoding="utf-8"))

    @app.get("/shop", response_class=HTMLResponse)
    def shop():
        return HTMLResponse((directory / "shop.html").read_text(encoding="utf-8"))

    return app


app = create_app()
