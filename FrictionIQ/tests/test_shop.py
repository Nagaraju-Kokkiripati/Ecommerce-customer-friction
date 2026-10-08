"""Connected journey tests with isolated persistent storage."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from api.main import create_app


class TestShop(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch("api.shop.get_settings", return_value=SimpleNamespace(DATA_DIR=Path(self.temp.name), ENV="development"))
        self.settings.start()
        self.client = TestClient(create_app())
        token = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        self.admin = {"Authorization": "Bearer " + token}

    def tearDown(self):
        self.client.close()
        self.settings.stop()
        self.temp.cleanup()

    def signup(self, consent=True, email="customer@example.com"):
        response = self.client.post("/api/shop/signup", json={"name": "Customer", "email": email, "password": "test-password", "consent": consent})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["session_id"]

    def pay(self, outcome):
        return self.client.post("/api/shop/payment", json={"outcome": outcome, "delivery_address": "123 Demo Street", "method": "demo_card"})

    def test_payment_friction_and_recovery_persists(self):
        sid = self.signup()
        self.client.post("/api/shop/events", json={"type": "product_view", "product_id": "p1"})
        cart = self.client.put("/api/shop/cart", json={"product_id": "p1", "quantity": 2}).json()
        self.assertEqual(cart["total"], 4998)
        self.client.post("/api/shop/events", json={"type": "checkout_start"})
        self.assertEqual(self.pay("failure").status_code, 200)
        self.assertEqual(self.pay("failure").status_code, 200)
        detail = self.client.get(f"/api/journeys/{sid}", headers=self.admin).json()
        self.assertIn("2 simulated payment failures", detail["facts"])
        self.assertGreaterEqual(detail["risk_score"], 70)
        self.assertIn("alternative", detail["recommendation"])
        self.assertEqual(self.client.get("/api/shop/orders").json(), [])
        recovery = self.client.post(f"/api/journeys/{sid}/recovery", headers=self.admin, json={"message": "Try the demo wallet."})
        self.assertEqual(recovery.json()["status"], "simulated")
        # A returning customer starts another session; outcome follows the customer.
        self.client.post("/api/shop/logout")
        login = self.client.post("/api/shop/login", json={"email": "customer@example.com", "password": "test-password"})
        self.assertNotEqual(login.json()["session_id"], sid)
        self.assertEqual(self.pay("success").status_code, 200)
        self.assertEqual(len(self.client.get("/api/shop/orders").json()), 1)
        self.assertEqual(self.client.get("/api/shop/cart").json()["items"], [])
        self.assertEqual(self.pay("success").status_code, 409)
        # Recreating the application does not lose orders, events, or recovery.
        with TestClient(create_app()) as fresh:
            result = fresh.get(f"/api/journeys/{sid}", headers=self.admin).json()
            self.assertEqual(result["recovery_outcome"], "purchase_after_simulated_action")
            self.assertEqual(len(result["recoveries"]), 1)

    def test_access_validation_and_consent(self):
        self.assertEqual(self.client.get("/api/shop/cart").status_code, 401)
        self.assertEqual(self.client.get("/api/journeys").status_code, 403)
        sid = self.signup(consent=False)
        cookie = self.client.cookies.get("shop_token")
        self.assertEqual(self.client.get("/api/journeys", headers={"Authorization": "Bearer " + cookie}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/journeys/{sid}/recovery", headers=self.admin, json={"message": "Hello"}).status_code, 409)
        self.assertEqual(self.client.put("/api/shop/cart", json={"product_id": "unknown", "quantity": 1}).status_code, 404)
        self.assertEqual(self.client.put("/api/shop/cart", json={"product_id": "p1", "quantity": -1}).status_code, 422)
        self.assertEqual(self.client.post("/api/shop/events", json={"type": "order_placed"}).status_code, 422)
        self.assertEqual(self.client.post("/api/shop/signup", json={"name": "Again", "email": "customer@example.com", "password": "test-password"}).status_code, 409)
        self.client.post("/api/shop/logout")
        self.assertEqual(self.client.get("/api/shop/cart").status_code, 401)
        self.assertEqual(self.client.post("/api/shop/login", json={"email": "customer@example.com", "password": "wrong"}).status_code, 401)

    def test_customer_isolation_and_search(self):
        first = self.signup()
        self.client.put("/api/shop/cart", json={"product_id": "p1", "quantity": 1})
        self.client.post("/api/shop/events", json={"type": "search_no_results", "query": "unknown"})
        self.client.post("/api/shop/logout")
        self.signup(email="other@example.com")
        self.assertEqual(self.client.get("/api/shop/cart").json()["total"], 0)
        detail = self.client.get(f"/api/journeys/{first}", headers=self.admin).json()
        self.assertIn("1 searches with no results", detail["facts"])
        self.assertIn("refine", detail["recommendation"])

    def test_storefront_and_dashboard_assets(self):
        for path in ("/shop", "/admin/journeys", "/static/js/shop.js", "/static/js/journeys.js", "/static/css/shop.css"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(len(self.client.get("/api/shop/products").json()), 6)
