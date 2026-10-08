"""
Tests for FrictionIQ FastAPI REST endpoints and SPA static serving.
"""
import unittest
from fastapi.testclient import TestClient
from api.main import app

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    def test_legacy_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

    def test_kpis(self):
        res = self.client.get("/api/kpis")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_sessions", data)
        self.assertIn("conversion_rate", data)
        self.assertIn("revenue_at_risk", data)
        self.assertGreater(data["total_sessions"], 0)

    def test_funnel(self):
        res = self.client.get("/api/funnel")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("stages", data)
        self.assertIsInstance(data["stages"], list)
        self.assertGreater(len(data["stages"]), 0)

    def test_friction_alerts(self):
        res = self.client.get("/api/friction/alerts")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("alerts", data)
        self.assertIsInstance(data["alerts"], list)

    def test_session_risk_prediction(self):
        payload = {
            "num_events": 15,
            "duration_sec": 340,
            "num_payment_fails": 2,
            "num_compares": 3,
            "reached_checkout": 1,
            "placed_order": 0,
        }
        res = self.client.post("/api/sessions/test_session_99/risk", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("risk_score", data)
        self.assertIn("risk_label", data)
        self.assertIn("session_id", data)

    def test_root_cause_analysis(self):
        payload = {
            "session_id": "test_session_101",
            "risk_score": 85.0,
            "features": {
                "num_payment_fails": 2,
                "reached_checkout": 1,
            },
            "payment_context": {"gateway": "Stripe", "failure_code": "insufficient_funds"},
            "feedback_text": "Card failed twice at final step",
        }
        res = self.client.post("/api/root-causes", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("root_causes", data)
        self.assertIn("recommended_interventions", data)
        self.assertIn("compliance_approved", data)

    def test_intervention_trigger(self):
        payload = {
            "session_id": "sess_recovery_1",
            "intervention_type": "alternate_payment_method",
            "channel": "in_app_modal",
            "message": "We noticed your card had an issue. Would you like to use UPI or NetBanking?",
            "approved_by": "admin",
        }
        res = self.client.post("/api/interventions/trigger", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("trigger_id", data)
        self.assertEqual(data["status"], "simulated")
        self.assertIn("no message was delivered", data["message"])

    def test_simulation(self):
        payload = {
            "intervention_type": "targeted_incentive_10pct",
            "audience_size": 2000,
            "baseline_conversion": 2.5,
            "incentive_pct": 10.0,
            "avg_order_value": 75.0,
        }
        res = self.client.post("/api/simulate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("revenue_recovered", data)
        self.assertIn("net_revenue", data)
        self.assertIn("roi", data)

    def test_model_metrics(self):
        res = self.client.get("/api/models/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("xgboost", data)

    def test_feedback_themes(self):
        res = self.client.get("/api/feedback/themes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("themes", data)

    def test_frontend_home(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("FrictionIQ", res.text)
        self.assertIn("app-shell", res.text)

if __name__ == "__main__":
    unittest.main()
