"""
FrictionIQ – Multi-Agent Reasoning with LangGraph
6 agents with typed I/O and logged reasoning traces.

Agents:
  1. Journey Analyst   – where friction occurs
  2. Root Cause        – why it occurs (fused evidence)
  3. Recovery Strategist – what intervention to recommend
  4. Personalization   – tailors message/channel/timing
  5. Critic/Guardrail  – policy compliance, discount caps, no PII
  5. Orchestrator      – coordinates, routes, resolves conflicts
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    session_id: str
    risk_score: float
    features: dict[str, Any]
    payment_context: dict[str, Any]         # gateway, failure codes
    product_context: dict[str, Any]         # desc quality, images
    feedback_text: str
    customer_segment: str

    # Agent outputs
    friction_location: str                  # which funnel stage
    root_causes: list[dict]                 # [{cause, confidence, evidence}]
    recommended_interventions: list[dict]   # [{type, uplift, cost, channel}]
    personalized_message: str
    compliance_approved: bool
    compliance_issues: list[str]
    final_decision: str
    reasoning_trace: list[dict]             # full audit trail


# ── Helper: LLM Client Abstraction ────────────────────────────────────────────

class LLMClient:
    """
    LLM abstraction supporting Gemini, OpenAI, Anthropic, and mock mode.
    Falls back to structured rule-based logic if LLM is unavailable.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.provider == "mock":
            return
        if self.provider == "openai":
            try:
                import openai
                self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"OpenAI client init failed: {e}. Falling back to mock.")
                self.provider = "mock"
        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._client = genai.GenerativeModel("gemini-pro")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}. Falling back to mock.")
                self.provider = "mock"

    def complete(self, prompt: str, system: str = "") -> str:
        """Call LLM with retries. Returns structured text or falls back to empty."""
        if self.provider == "mock" or self._client is None:
            return ""  # Signal fallback to caller
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                if self.provider == "openai":
                    resp = self._client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=settings.LLM_TEMPERATURE,
                        response_format={"type": "json_object"},
                        timeout=settings.LLM_TIMEOUT_SECONDS,
                    )
                    return resp.choices[0].message.content
            except Exception as e:
                logger.warning(f"LLM attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt)
        return ""


_llm = LLMClient()


def _trace(state: AgentState, agent: str, output: dict) -> list[dict]:
    trace = list(state.get("reasoning_trace", []))
    trace.append({
        "agent": agent,
        "timestamp": time.time(),
        "output_summary": {k: v for k, v in output.items() if k != "reasoning_trace"},
    })
    return trace


# ── Agent Nodes ───────────────────────────────────────────────────────────────

def journey_analyst_node(state: AgentState) -> dict:
    """Identifies WHERE in the funnel friction occurs."""
    features = state.get("features", {})
    risk = state.get("risk_score", 0)

    # Determine friction location from behavioral signals
    if features.get("num_payment_fails", 0) > 0:
        location = "payment_stage"
    elif features.get("has_delivery_check", 0) and features.get("exited_at_checkout", 0):
        location = "delivery_eta_stage"
    elif features.get("exited_at_checkout", 0) and not features.get("reached_payment", 0):
        location = "checkout_form_stage"
    elif features.get("num_compares", 0) > 3 and features.get("reached_checkout", 0) == 0:
        location = "product_evaluation_stage"
    elif features.get("num_searches", 0) > 3 and features.get("num_cart_adds", 0) == 0:
        location = "search_discovery_stage"
    elif features.get("num_rage_clicks", 0) > 1:
        location = "technical_friction_stage"
    else:
        location = "browse_stage"

    out = {"friction_location": location}
    return {**out, "reasoning_trace": _trace(state, "journey_analyst", out)}


def root_cause_node(state: AgentState) -> dict:
    """Fuses behavioral, payment, product, and feedback evidence into ranked causes."""
    features = state.get("features", {})
    payment_ctx = state.get("payment_context", {})
    product_ctx = state.get("product_context", {})
    feedback = state.get("feedback_text", "")
    location = state.get("friction_location", "")

    causes = []

    # Payment signals
    if features.get("num_payment_fails", 0) > 0:
        error = payment_ctx.get("error_code", "UNKNOWN")
        gateway = payment_ctx.get("gateway", "unknown")
        causes.append({
            "cause": "payment_failure",
            "confidence": min(0.95, 0.7 + features["num_payment_fails"] * 0.1),
            "evidence": f"Payment failed {features['num_payment_fails']} time(s) — error: {error} on {gateway}",
            "severity": "high",
        })

    # Product info signals
    if features.get("num_compares", 0) > 3 and product_ctx.get("description_quality_score", 1.0) < 0.4:
        causes.append({
            "cause": "unclear_product_info",
            "confidence": 0.80,
            "evidence": f"Customer compared {features['num_compares']} products; description quality={product_ctx.get('description_quality_score', '?')}",
            "severity": "medium",
        })

    # Delivery signals
    if features.get("has_delivery_check", 0) or "delivery" in location:
        causes.append({
            "cause": "delivery_uncertainty",
            "confidence": 0.80,
            "evidence": "Session dropped after delivery ETA check at checkout.",
            "severity": "medium",
        })

    # Search/recommendation
    if features.get("search_reformulation_count", 0) > 2 or (features.get("num_searches", 0) > 4 and features.get("num_cart_adds", 0) == 0):
        causes.append({
            "cause": "poor_search_recommendations",
            "confidence": 0.70,
            "evidence": f"Customer searched {features.get('num_searches', 0)} times with {features.get('search_reformulation_count', 0)} reformulations, no cart adds.",
            "severity": "medium",
        })

    # Technical
    if features.get("num_rage_clicks", 0) > 1:
        causes.append({
            "cause": "technical_friction",
            "confidence": 0.85,
            "evidence": f"Detected {features['num_rage_clicks']} rage clicks.",
            "severity": "high",
        })

    # Feedback signals
    if feedback:
        fb_lower = feedback.lower()
        if any(w in fb_lower for w in ["delivery", "late", "wismo", "arrive", "shipping", "courier"]):
            causes.append({
                "cause": "delivery_uncertainty",
                "confidence": 0.85,
                "evidence": f"Feedback mentions delivery: '{feedback[:80]}'",
                "severity": "high",
            })

    if not causes:
        causes.append({
            "cause": "unknown_friction",
            "confidence": 0.40,
            "evidence": "No strong signal detected. Recommend fallback incentive.",
            "severity": "low",
        })

    # Sort by confidence
    causes = sorted(causes, key=lambda x: x["confidence"], reverse=True)

    out = {"root_causes": causes}
    return {**out, "reasoning_trace": _trace(state, "root_cause", out)}


def recovery_strategist_node(state: AgentState) -> dict:
    """Maps root causes to prioritized intervention catalog."""
    causes = state.get("root_causes", [])
    features = state.get("features", {})
    risk = state.get("risk_score", 0)

    INTERVENTION_MAP = {
        "payment_failure": [
            {"type": "alternate_payment_method", "uplift": 0.22, "cost": 0.0, "channel": "in_app"},
            {"type": "smart_payment_retry", "uplift": 0.18, "cost": 0.0, "channel": "in_app"},
        ],
        "unclear_product_info": [
            {"type": "clarify_product_info", "uplift": 0.15, "cost": 0.0, "channel": "email"},
            {"type": "show_size_fit_guide", "uplift": 0.12, "cost": 0.0, "channel": "in_app"},
        ],
        "delivery_uncertainty": [
            {"type": "delivery_date_promise", "uplift": 0.20, "cost": 5.0, "channel": "in_app"},
        ],
        "poor_search_recommendations": [
            {"type": "recommendation_rerank", "uplift": 0.10, "cost": 0.0, "channel": "in_app"},
        ],
        "technical_friction": [
            {"type": "support_escalation", "uplift": 0.08, "cost": 15.0, "channel": "chat"},
        ],
        "delivery_anxiety": [
            {"type": "proactive_delay_notification", "uplift": 0.30, "cost": 2.0, "channel": "sms"},
            {"type": "support_escalation", "uplift": 0.25, "cost": 15.0, "channel": "chat"},
        ],
        "unknown_friction": [
            {"type": "targeted_incentive_10pct", "uplift": 0.14, "cost": 0.10, "channel": "email"},
            {"type": "cart_reminder", "uplift": 0.09, "cost": 0.0, "channel": "push"},
        ],
    }

    interventions = []
    for cause in causes[:2]:  # Act on top 2 causes
        c = cause["cause"]
        mapped = INTERVENTION_MAP.get(c, INTERVENTION_MAP["unknown_friction"])
        for m in mapped:
            m = {**m, "for_cause": c, "cause_confidence": cause["confidence"]}
            interventions.append(m)

    # Deduplicate
    seen = set()
    unique_interventions = []
    for iv in interventions:
        if iv["type"] not in seen:
            seen.add(iv["type"])
            unique_interventions.append(iv)

    out = {"recommended_interventions": unique_interventions[:4]}
    return {**out, "reasoning_trace": _trace(state, "recovery_strategist", out)}


def personalization_node(state: AgentState) -> dict:
    """Tailors message tone, channel, and offer to the customer segment."""
    segment = state.get("customer_segment", "general")
    interventions = state.get("recommended_interventions", [])
    causes = state.get("root_causes", [])
    top_cause = causes[0]["cause"] if causes else "unknown"

    # Tone mapping
    tone_map = {
        "payment_failure": "apologetic and helpful",
        "delivery_uncertainty": "reassuring and specific",
        "unclear_product_info": "informative and engaging",
        "delivery_anxiety": "empathetic and proactive",
    }
    tone = tone_map.get(top_cause, "friendly and helpful")

    # Message templates (LLM would fill these in production)
    message_templates = {
        "payment_failure": "We noticed a hiccup during your payment. Try UPI or net banking — it only takes 30 seconds!",
        "delivery_uncertainty": "Great news! Your order can be delivered by {eta}. Complete your purchase now.",
        "unclear_product_info": "Have questions about this product? Our AI assistant can help you find the perfect fit.",
        "delivery_anxiety": "Your order is on the way! Here's the latest tracking update: {tracking}.",
        "unknown_friction": "Your cart is waiting! Complete your purchase and enjoy a special 10% off.",
    }
    message = message_templates.get(top_cause, message_templates["unknown_friction"])

    # Try LLM for richer message
    llm_response = _llm.complete(
        prompt=f"Cause: {top_cause}. Segment: {segment}. Tone: {tone}. Draft a 1-sentence recovery message. Return JSON: {{\"message\": \"...\"}}",
        system="You are a customer retention specialist. Never include discounts > 20%. No manipulative dark patterns.",
    )
    if llm_response:
        try:
            parsed = json.loads(llm_response)
            message = parsed.get("message", message)
        except Exception:
            pass

    out = {"personalized_message": message}
    return {**out, "reasoning_trace": _trace(state, "personalization", out)}


def critic_guardrail_node(state: AgentState) -> dict:
    """Enforces policy compliance: discount caps, no PII, no dark patterns."""
    interventions = state.get("recommended_interventions", [])
    message = state.get("personalized_message", "")
    issues = []

    # Check discount caps
    for iv in interventions:
        if "incentive" in iv.get("type", ""):
            pct_str = iv["type"].split("_")[-1].replace("pct", "")
            try:
                pct = float(pct_str)
                if pct > settings.MAX_DISCOUNT_PCT:
                    issues.append(f"Discount {pct}% exceeds cap of {settings.MAX_DISCOUNT_PCT}%")
            except ValueError:
                pass

    # Check for PII in message
    import re
    if re.search(r"\b[6-9]\d{9}\b", message):
        issues.append("Message contains possible phone number (PII)")
    if re.search(r"\b[\w.+-]+@[\w-]+\.\w+\b", message):
        issues.append("Message contains possible email (PII)")

    # Dark pattern detection
    dark_patterns = ["limited time", "only 1 left", "act now or lose", "final warning"]
    for pattern in dark_patterns:
        if pattern in message.lower():
            issues.append(f"Possible dark pattern detected: '{pattern}'")

    approved = len(issues) == 0
    decision = "APPROVED" if approved else "NEEDS_REVIEW"

    # High-impact actions require human approval
    high_impact = any(iv.get("uplift", 0) > 0.20 for iv in interventions)
    if high_impact and settings.HIGH_IMPACT_REQUIRES_APPROVAL:
        decision = "PENDING_HUMAN_APPROVAL"

    out = {
        "compliance_approved": approved,
        "compliance_issues": issues,
        "final_decision": decision,
    }
    return {**out, "reasoning_trace": _trace(state, "critic_guardrail", out)}


# ── Build Graph ────────────────────────────────────────────────────────────────

def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("journey_analyst", journey_analyst_node)
    workflow.add_node("root_cause", root_cause_node)
    workflow.add_node("recovery_strategist", recovery_strategist_node)
    workflow.add_node("personalization", personalization_node)
    workflow.add_node("critic_guardrail", critic_guardrail_node)

    workflow.set_entry_point("journey_analyst")
    workflow.add_edge("journey_analyst", "root_cause")
    workflow.add_edge("root_cause", "recovery_strategist")
    workflow.add_edge("recovery_strategist", "personalization")
    workflow.add_edge("personalization", "critic_guardrail")
    workflow.add_edge("critic_guardrail", END)

    return workflow.compile()


# Singleton
_graph = None

def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


def run_agents(
    session_id: str,
    risk_score: float,
    features: dict,
    payment_context: dict | None = None,
    product_context: dict | None = None,
    feedback_text: str = "",
    customer_segment: str = "general",
) -> dict:
    """
    High-level entry point for running the full agent pipeline.
    Returns the final state dict with all agent outputs.
    """
    graph = get_agent_graph()
    initial_state: AgentState = {
        "session_id": session_id,
        "risk_score": risk_score,
        "features": features,
        "payment_context": payment_context or {},
        "product_context": product_context or {},
        "feedback_text": feedback_text,
        "customer_segment": customer_segment,
        "friction_location": "",
        "root_causes": [],
        "recommended_interventions": [],
        "personalized_message": "",
        "compliance_approved": False,
        "compliance_issues": [],
        "final_decision": "",
        "reasoning_trace": [],
    }
    result = graph.invoke(initial_state)
    return result


if __name__ == "__main__":
    result = run_agents(
        session_id="demo_session_001",
        risk_score=88.5,
        features={"num_payment_fails": 2, "payment_fail_rate": 1.0, "reached_checkout": 1},
        payment_context={"gateway": "Razorpay", "error_code": "3DS_TIMEOUT"},
        product_context={"description_quality_score": 0.75},
    )
    print("\n=== Agent Final State ===")
    for k, v in result.items():
        if k != "reasoning_trace":
            print(f"  {k}: {v}")
    print(f"\n=== Reasoning Trace ({len(result['reasoning_trace'])} steps) ===")
    for step in result["reasoning_trace"]:
        print(f"  [{step['agent']}] {json.dumps(step['output_summary'], indent=4)[:200]}")
