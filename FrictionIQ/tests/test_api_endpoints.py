"""Live analytics must be empty without captured data and require authentication."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import create_app
from core.config import get_settings


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        config = get_settings().model_copy(update={"DATA_DIR": Path(self.temp.name)})
        self.patch = patch("api.shop.get_settings", return_value=config)
        self.patch.start()
        self.client = TestClient(create_app())
        token = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        self.headers = {"Authorization": "Bearer " + token}

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.temp.cleanup()

    def test_empty_analytics_are_not_fabricated(self):
        kpis = self.client.get("/api/kpis", headers=self.headers).json()
        self.assertEqual(kpis["total_sessions"], 0)
        self.assertEqual(kpis["order_revenue"], 0)
        self.assertEqual(kpis["source"], "captured_events")
        self.assertEqual(self.client.get("/api/friction/alerts", headers=self.headers).json()["alerts"], [])
        self.assertEqual(self.client.get("/api/feedback/themes", headers=self.headers).json()["themes"], [])
        self.assertEqual(sum(s["sessions"] for s in self.client.get("/api/funnel", headers=self.headers).json()["stages"]), 0)

    def test_request_connection_can_move_between_workers(self):
        from api.shop import database
        dependency = database()
        with ThreadPoolExecutor(max_workers=1) as creator, ThreadPoolExecutor(max_workers=1) as endpoint:
            db = creator.submit(next, dependency).result()
            try:
                count = endpoint.submit(lambda: db.execute("SELECT COUNT(*) FROM journeys").fetchone()[0]).result()
                self.assertEqual(count, 0)
            finally:
                endpoint.submit(dependency.close).result()

    def test_parallel_dashboard_refresh(self):
        # Initialize schema, then reproduce the dashboard's simultaneous reads.
        self.client.get("/api/kpis", headers=self.headers)
        paths = ["/api/kpis", "/api/journeys", "/api/funnel"] * 8
        with ThreadPoolExecutor(max_workers=6) as workers:
            responses = list(workers.map(lambda path: self.client.get(path, headers=self.headers), paths))
        self.assertTrue(all(response.status_code == 200 for response in responses))

    def test_analytics_follow_checkout(self):
        self.client.post("/api/shop/signup", json={"name": "Test", "email": "test@example.com", "password": "password123"})
        self.client.post("/api/shop/events", json={"type": "product_view", "product_id": "p1"})
        self.client.put("/api/shop/cart", json={"product_id": "p1", "quantity": 1})
        self.client.post("/api/shop/events", json={"type": "checkout_start"})
        self.client.post("/api/shop/payment", json={"outcome": "failure", "delivery_address": "123 Demo Street"})
        kpis = self.client.get("/api/kpis", headers=self.headers).json()
        self.assertEqual(kpis["payment_failures"], 1)
        self.assertEqual(kpis["revenue_at_risk"], 2499)
        self.client.post("/api/shop/payment", json={"outcome": "success", "delivery_address": "123 Demo Street"})
        kpis = self.client.get("/api/kpis", headers=self.headers).json()
        self.assertEqual(kpis["conversion_rate"], 100)
        self.assertEqual(kpis["order_revenue"], 2499)
        self.assertEqual(kpis["revenue_at_risk"], 0)

    def test_admin_authentication_required(self):
        for path in ("/api/kpis", "/api/funnel", "/api/models/metrics", "/api/audit-log", "/api/journeys"):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code, 401)

    def test_model_provenance_without_fake_accuracy(self):
        model = self.client.get("/api/models/metrics", headers=self.headers).json()
        self.assertEqual(model["model"], "xgboost_v1")
        self.assertIsNone(model["live_validation_metrics"])
        self.assertEqual(model["llm"], "none")

    def test_pages_and_unknown_sessions(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "healthy")
        for path in ("/", "/admin", "/admin/journeys", "/shop"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.post("/api/sessions/missing/risk", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get("/api/stream/events").status_code, 404)
