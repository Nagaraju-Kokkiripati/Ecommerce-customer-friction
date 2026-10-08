"""
FrictionIQ - Comprehensive End-to-End Test Suite
Tests all 13 core workflows including live API, ML models, multi-agent reasoning,
counterfactual simulation, governance audit logs, and frontend static assets.
"""
import requests
import json
import time

BASE = "http://localhost:8000"

def run_tests():
    print("=" * 60)
    print("FRICTIONIQ END-TO-END APPLICATION TEST RUN")
    print("=" * 60)

    # 1. Health
    r = requests.get(f"{BASE}/api/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print("[PASS] 1. Health Check:", r.json().get("status"))

    # 2. SPA Index & HTML Shell
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200 and "FrictionIQ" in r.text
    assert "app-shell" in r.text
    print(f"[PASS] 2. SPA Index Serving: 200 OK ({len(r.text)} bytes)")

    # 3. Static Assets
    for asset in ["/static/css/main.css", "/static/js/app.js"]:
        r = requests.get(f"{BASE}{asset}")
        assert r.status_code == 200, f"Static asset {asset} failed"
        print(f"[PASS] 3. Static Asset {asset}: 200 OK ({len(r.text)} bytes)")

    # 4. KPIs
    r = requests.get(f"{BASE}/api/kpis")
    assert r.status_code == 200
    kpis = r.json()
    print("[PASS] 4. Executive KPIs:", {
        "Total Sessions": kpis.get("total_sessions"),
        "Conversion Rate": f"{kpis.get('conversion_rate')}%",
        "Revenue at Risk": f"${kpis.get('revenue_at_risk'):,.2f}",
        "Recovered": f"${kpis.get('revenue_recovered'):,.2f}"
    })

    # 5. Funnel Stages
    r = requests.get(f"{BASE}/api/funnel")
    assert r.status_code == 200
    stages = r.json().get("stages", [])
    print(f"[PASS] 5. Journey Funnel: {len(stages)} stages loaded")
    for s in stages[:3]:
        print(f"       - {s['stage']}: {s['sessions']} sessions (drop-off: {s['drop_off_rate']}%, risk: ${s['revenue_at_risk']:,.2f})")

    # 6. Friction Alerts
    r = requests.get(f"{BASE}/api/friction/alerts")
    assert r.status_code == 200
    alerts = r.json().get("alerts", [])
    print(f"[PASS] 6. Friction Alerts: {len(alerts)} alerts active")
    for a in alerts[:2]:
        print(f"       - [{a.get('severity','').upper()}] {a.get('friction_type')}: {a.get('session_count')} sessions (${a.get('revenue_at_risk', 0):,.2f} at risk)")

    # 7. Session Risk Prediction (ML + SHAP)
    session_feat = {
        "num_events": 18,
        "duration_sec": 410,
        "num_payment_fails": 2,
        "num_compares": 4,
        "reached_checkout": 1,
        "placed_order": 0,
        "has_delivery_check": 1
    }
    r = requests.post(f"{BASE}/api/sessions/sess_test_901/risk", json=session_feat)
    assert r.status_code == 200
    risk_data = r.json()
    print(f"[PASS] 7. ML Session Risk: Score={risk_data.get('risk_score')}, Label={risk_data.get('risk_label')}, Model={risk_data.get('model')}")

    # 8. LangGraph Multi-Agent Root Cause & Recommendations
    agent_req = {
        "session_id": "sess_test_901",
        "risk_score": risk_data.get("risk_score", 85.0),
        "features": session_feat,
        "payment_context": {"gateway": "Razorpay", "error_code": "CARD_DECLINED_INSUFFICIENT_FUNDS"},
        "feedback_text": "Card kept failing at payment step, wanted to pay via UPI",
        "customer_segment": "VIP"
    }
    r = requests.post(f"{BASE}/api/root-causes", json=agent_req)
    assert r.status_code == 200
    agent_res = r.json()
    top_cause = agent_res.get("root_causes", [{}])[0]
    top_rec = agent_res.get("recommended_interventions", [{}])[0]
    print("[PASS] 8. Multi-Agent Reasoning Graph:")
    print(f"       - Top Root Cause: {top_cause.get('cause')} (confidence: {top_cause.get('confidence')})")
    print(f"       - Evidence: {top_cause.get('evidence')}")
    print(f"       - Recommended Intervention: {top_rec.get('type')}")
    print(f"       - Compliance Approved: {agent_res.get('compliance_approved')}")

    # 9. Intervention Trigger & Audit Trail
    trig_req = {
        "session_id": "sess_test_901",
        "intervention_type": "alternate_payment_method",
        "channel": "in_app_modal",
        "message": "We noticed your card had an issue. Would you like to complete payment with UPI or NetBanking?",
        "approved_by": "lead_ops"
    }
    r = requests.post(f"{BASE}/api/interventions/trigger", json=trig_req)
    assert r.status_code == 200
    trig_res = r.json()
    print(f"[PASS] 9. Intervention Trigger: ID={trig_res.get('trigger_id')}, Status={trig_res.get('status')}")

    # 10. Audit Log Retrieval
    r = requests.get(f"{BASE}/api/audit-log")
    assert r.status_code == 200
    logs = r.json().get("entries", [])
    print(f"[PASS] 10. Governance Audit Log: {len(logs)} entries retrieved (latest: {logs[0].get('action')} by {logs[0].get('actor')})")

    # 11. Recovery Simulation
    sim_req = {
        "intervention_type": "targeted_incentive_10pct",
        "audience_size": 2500,
        "baseline_conversion": 2.8,
        "incentive_pct": 10.0,
        "avg_order_value": 85.0
    }
    r = requests.post(f"{BASE}/api/simulate", json=sim_req)
    assert r.status_code == 200
    sim_res = r.json()
    print("[PASS] 11. Counterfactual Simulator:")
    print(f"       - Expected Conversions: {sim_res.get('expected_conversions')}")
    print(f"       - Revenue Recovered: ${sim_res.get('revenue_recovered'):,.2f}")
    print(f"       - Net Profit Lift: ${sim_res.get('net_revenue'):,.2f}")
    print(f"       - Simulated ROI: {sim_res.get('roi')}%")

    # 12. Feedback Intelligence
    r = requests.get(f"{BASE}/api/feedback/themes")
    assert r.status_code == 200
    themes = r.json().get("themes", [])
    print(f"[PASS] 12. Feedback Intelligence: {len(themes)} clusters found")
    for t in themes[:2]:
        print(f"       - {t['theme']}: {t['count']} mentions (sentiment: {t['avg_sentiment']})")

    # 13. Streamlit Compatibility API
    st_req = {"session_id": "streamlit_test_1", "features": {"payment_fail": 2, "checkout_start": 1}}
    r = requests.post(f"{BASE}/friction/root-causes", json=st_req)
    assert r.status_code == 200
    st_res = r.json()
    print(f"[PASS] 13. Streamlit Compatibility: root_cause={st_res.get('root_cause')}, rec={st_res.get('recommended_intervention')}")

    print("=" * 60)
    print("ALL 13 END-TO-END APPLICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
