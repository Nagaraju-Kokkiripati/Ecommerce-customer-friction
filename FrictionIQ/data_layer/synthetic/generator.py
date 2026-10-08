"""
FrictionIQ – Comprehensive Synthetic Data Generator
Produces ~50k realistic e-commerce sessions with:
- 8 labeled friction patterns (ground truth kept separate)
- Payment logs with realistic failure codes
- Delivery checks with pincode/ETA data
- Support tickets and chat transcripts
- Recovery responses with conversion outcomes

Seeded for reproducibility. All IDs are salted-hash anonymized.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker("en_IN")  # Indian locale for realism

# ── Constants ────────────────────────────────────────────────────────────────
FRICTION_TYPES = [
    "unclear_product_info",
    "delivery_uncertainty",
    "payment_failure",
    "poor_recommendations",
    "price_shock",
    "trust_policy_concern",
    "technical_friction",
    "post_purchase_anxiety",
]

EVENT_TYPES = [
    "page_view", "search", "product_view", "compare",
    "add_to_cart", "remove_from_cart", "checkout_start",
    "address_entry", "delivery_check", "payment_attempt",
    "payment_fail", "order_placed", "exit",
    "rage_click", "dead_click",
]

DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.62, 0.30, 0.08]

CHANNELS = ["organic", "paid_search", "social", "email", "direct", "affiliate"]
CHANNEL_WEIGHTS = [0.35, 0.22, 0.18, 0.10, 0.10, 0.05]

CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Beauty", "Sports", "Books", "Toys", "Grocery"]

GATEWAYS = ["Razorpay", "PayU", "CCAvenue", "Stripe", "Paytm", "PhonePe"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet", "cod", "bnpl"]
FAILURE_CODES = [
    "3DS_TIMEOUT", "INSUFFICIENT_FUNDS", "BANK_DECLINE",
    "UPI_PENDING", "COD_UNAVAILABLE", "GATEWAY_5XX",
    "CARD_EXPIRED", "VPA_INVALID",
]

REVIEW_TEMPLATES = {
    "delivery": [
        "My order took forever to arrive. Tracking was useless.",
        "Promised 3 days, took 12. Very disappointed.",
        "Delivery was late but product is fine.",
        "Super fast delivery! Got it next day.",
    ],
    "product_info": [
        "Product images were misleading. Completely different from what I expected.",
        "No size guide available. Had to guess and got wrong size.",
        "Description was accurate and helpful.",
        "Couldn't find specifications I needed before buying.",
    ],
    "payment": [
        "Payment kept failing. Took 4 tries to complete the order.",
        "UPI payment was smooth and instant.",
        "Credit card declined twice for no reason.",
        "Great checkout experience, very seamless.",
    ],
    "post_purchase": [
        "Where is my order? No tracking update for 5 days!",
        "Return process was a nightmare.",
        "Refund processed quickly, thank you.",
        "Support team was helpful and resolved my issue.",
    ],
    "general_positive": [
        "Excellent product quality! Highly recommended.",
        "Great value for money.",
        "Fast shipping, product as described.",
        "Will definitely buy again!",
    ],
}

TICKET_TEMPLATES = {
    "WISMO": [
        "Where is my order? It has been {days} days since I ordered.",
        "My tracking hasn't updated in {days} days. Please help!",
        "Order #{order_id} is showing 'in transit' for too long.",
    ],
    "payment": [
        "My payment was deducted but order not confirmed.",
        "Got a bank decline but I have sufficient balance.",
        "UPI payment failed, money debited. Please refund immediately.",
    ],
    "return": [
        "I want to return this product, it's defective.",
        "Return pickup not happening despite multiple requests.",
        "Refund not received even after 7 days of return pickup.",
    ],
    "product_info": [
        "Size guide on website is wrong. Got wrong size.",
        "Product is completely different from images.",
        "Description missing key specifications.",
    ],
}

INTERVENTION_CATALOG = [
    "clarify_product_info",
    "show_size_fit_guide",
    "delivery_date_promise",
    "alternate_payment_method",
    "smart_payment_retry",
    "targeted_incentive_5pct",
    "targeted_incentive_10pct",
    "targeted_incentive_15pct",
    "proactive_delay_notification",
    "support_escalation",
    "recommendation_rerank",
    "cart_reminder",
    "trust_nudge_reviews",
    "trust_nudge_return_policy",
]


def _hash_id(raw_id: str, salt: str = "frictioniq_v2") -> str:
    return hashlib.sha256(f"{raw_id}{salt}".encode()).hexdigest()[:20]


def _redact_pii(text: str) -> str:
    """Replace phone numbers and email-like patterns with [REDACTED]."""
    import re
    text = re.sub(r"\b[6-9]\d{9}\b", "[REDACTED_PHONE]", text)
    text = re.sub(r"\b[\w.+-]+@[\w-]+\.\w+\b", "[REDACTED_EMAIL]", text)
    return text


class SyntheticGenerator:
    """
    Generates all synthetic e-commerce data tables.
    All public-dataset gaps are filled by this generator.
    """

    def __init__(self, n_sessions: int = 50_000, seed: int = 42, output_dir: str = "data/processed"):
        self.n_sessions = n_sessions
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        random.seed(seed)
        np.random.seed(seed)
        Faker.seed(seed)

        # Internal state
        self._products: list[dict] = []
        self._sessions: list[dict] = []
        self._events: list[dict] = []
        self._payments: list[dict] = []
        self._delivery_checks: list[dict] = []
        self._reviews: list[dict] = []
        self._tickets: list[dict] = []
        self._orders: list[dict] = []
        self._recovery: list[dict] = []
        self._ground_truth: list[dict] = []

    # ── Products ─────────────────────────────────────────────────────────────

    def _gen_products(self, n: int = 2000) -> None:
        print(f"  Generating {n} products...")
        for _ in range(n):
            pid = f"P{fake.unique.random_number(digits=7)}"
            cat = random.choice(CATEGORIES)
            desc_score = np.random.beta(3, 2)   # skew towards reasonable quality
            price = round(np.random.lognormal(7, 1.2), 2)  # realistic price distribution
            self._products.append({
                "product_id": pid,
                "category": cat,
                "subcategory": fake.word(),
                "price": max(49.0, min(price, 150_000.0)),
                "description_quality_score": round(desc_score, 3),
                "image_count": max(0, int(np.random.poisson(4) * desc_score)),
                "stock": int(np.random.exponential(200)),
                "delivery_eta_days": random.choices([1, 2, 3, 5, 7, 10, 14], weights=[5, 15, 30, 25, 15, 7, 3])[0],
                "return_policy": random.choices(["30_days", "15_days", "7_days", "no_return"], weights=[50, 25, 15, 10])[0],
                "rating": round(np.random.beta(5, 2) * 4 + 1, 1),
                "review_count": int(np.random.exponential(80)),
                "seller_id": _hash_id(str(random.randint(1, 500))),
            })

    # ── Sessions ──────────────────────────────────────────────────────────────

    def _gen_sessions(self) -> None:
        print(f"  Generating {self.n_sessions} sessions...")
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 10, 1)
        delta = (end_date - start_date).days

        for _ in range(self.n_sessions):
            sid = str(uuid.uuid4())
            raw_cid = fake.uuid4() if random.random() > 0.25 else f"guest_{uuid.uuid4()}"
            cid = _hash_id(raw_cid)
            start = start_date + timedelta(
                days=random.randint(0, delta),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            self._sessions.append({
                "session_id": sid,
                "customer_id": cid,
                "start_time": start,
                "device": random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0],
                "channel": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0],
                "country": "IN",
                "is_new_customer": random.random() < 0.45,
            })

    # ── Events & Friction Patterns ────────────────────────────────────────────

    def _add_event(self, session: dict, event_type: str, page: str,
                   ts: datetime, product: Optional[dict] = None,
                   extra: Optional[dict] = None) -> datetime:
        self._events.append({
            "event_id": str(uuid.uuid4()),
            "session_id": session["session_id"],
            "customer_id": session["customer_id"],
            "timestamp": ts,
            "event_type": event_type,
            "page": page,
            "product_id": product["product_id"] if product else None,
            "device": session["device"],
            "channel": session["channel"],
            "country": session["country"],
            **(extra or {}),
        })
        return ts

    def _gen_events(self) -> None:
        print("  Generating events with friction patterns...")
        products_df = pd.DataFrame(self._products)

        # Weight friction types - bounce is most common; each explicit friction ~5-8%
        friction_weights = [6, 5, 6, 5, 5, 4, 4, 5, 25, 35]
        friction_choices = FRICTION_TYPES + ["no_friction", "bounce"]

        for session in self._sessions:
            friction = random.choices(friction_choices, weights=friction_weights)[0]
            ts = session["start_time"]

            # Every session starts with page_view home
            ts += timedelta(seconds=random.randint(1, 5))
            self._add_event(session, "page_view", "home", ts)

            if friction == "bounce":
                ts += timedelta(seconds=random.randint(5, 45))
                self._add_event(session, "exit", "home", ts)
                self._ground_truth.append({"session_id": session["session_id"], "friction_label": "bounce", "is_abandoned": 1})
                continue

            # Pick a target product
            cat_filter = products_df[products_df["description_quality_score"] < 0.3] if friction == "unclear_product_info" else products_df
            if len(cat_filter) == 0:
                cat_filter = products_df
            target = cat_filter.sample(1).iloc[0].to_dict()

            if friction == "unclear_product_info":
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "search", "search", ts, extra={"query": target["subcategory"]})
                for _ in range(random.randint(3, 6)):
                    ts += timedelta(seconds=random.randint(15, 90))
                    self._add_event(session, "product_view", "product_detail", ts, target)
                    ts += timedelta(seconds=random.randint(5, 20))
                    self._add_event(session, "compare", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "exit", "product_detail", ts, target)

            elif friction == "delivery_uncertainty":
                ts += timedelta(seconds=random.randint(15, 45))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "add_to_cart", "cart", ts, target)
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "checkout_start", "checkout", ts)
                ts += timedelta(seconds=random.randint(15, 40))
                self._add_event(session, "address_entry", "checkout", ts)
                ts += timedelta(seconds=random.randint(5, 15))
                # Delivery check – high ETA
                pincode = fake.postcode()
                eta = random.randint(8, 21)
                self._delivery_checks.append({
                    "check_id": str(uuid.uuid4()),
                    "session_id": session["session_id"],
                    "product_id": target["product_id"],
                    "timestamp": ts,
                    "pincode": pincode,
                    "promised_eta_days": eta,
                    "is_serviceable": True,
                    "shipping_fee": round(random.uniform(49, 199), 2),
                })
                self._add_event(session, "delivery_check", "checkout", ts, target)
                ts += timedelta(seconds=random.randint(5, 20))
                self._add_event(session, "exit", "checkout", ts)

            elif friction == "payment_failure":
                ts += timedelta(seconds=random.randint(15, 40))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "add_to_cart", "cart", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "checkout_start", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 50))
                self._add_event(session, "address_entry", "checkout", ts)
                n_fails = random.randint(1, 3)
                gateway = random.choice(GATEWAYS)
                method = random.choices(PAYMENT_METHODS, weights=[30, 35, 10, 10, 10, 5])[0]
                for attempt in range(1, n_fails + 1):
                    ts += timedelta(seconds=random.randint(20, 60))
                    self._add_event(session, "payment_attempt", "checkout", ts)
                    error = random.choice(FAILURE_CODES)
                    self._payments.append({
                        "payment_id": str(uuid.uuid4()),
                        "session_id": session["session_id"],
                        "timestamp": ts,
                        "gateway": gateway,
                        "method": method,
                        "amount": round(target["price"] * random.uniform(1.0, 1.18), 2),
                        "currency": "INR",
                        "status": "failed",
                        "error_code": error,
                        "latency_ms": random.randint(500, 8000),
                        "attempt_number": attempt,
                    })
                    ts += timedelta(seconds=random.randint(2, 8))
                    self._add_event(session, "payment_fail", "checkout", ts)
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "exit", "checkout", ts)

            elif friction == "poor_recommendations":
                for _ in range(random.randint(3, 5)):
                    ts += timedelta(seconds=random.randint(10, 30))
                    query = fake.word()
                    self._add_event(session, "search", "search", ts, extra={"query": query, "results_count": random.choices([0, random.randint(1, 5)], weights=[30, 70])[0]})
                    ts += timedelta(seconds=random.randint(5, 20))
                    self._add_event(session, "page_view", "recommendation_widget", ts)
                ts += timedelta(seconds=random.randint(5, 15))
                self._add_event(session, "exit", "search_results", ts)

            elif friction == "price_shock":
                ts += timedelta(seconds=random.randint(15, 40))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "add_to_cart", "cart", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "checkout_start", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 45))
                self._add_event(session, "address_entry", "checkout", ts)
                # Delivery check with high fee
                self._delivery_checks.append({
                    "check_id": str(uuid.uuid4()),
                    "session_id": session["session_id"],
                    "product_id": target["product_id"],
                    "timestamp": ts,
                    "pincode": fake.postcode(),
                    "promised_eta_days": random.randint(3, 7),
                    "is_serviceable": True,
                    "shipping_fee": round(random.uniform(150, 499), 2),  # high fee = shock
                })
                ts += timedelta(seconds=random.randint(5, 15))
                self._add_event(session, "exit", "checkout_summary", ts)

            elif friction == "trust_policy_concern":
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(5, 20))
                self._add_event(session, "page_view", "reviews", ts, target)
                ts += timedelta(seconds=random.randint(10, 30))
                self._add_event(session, "page_view", "return_policy", ts)
                ts += timedelta(seconds=random.randint(5, 20))
                self._add_event(session, "exit", "return_policy", ts)

            elif friction == "technical_friction":
                ts += timedelta(seconds=random.randint(5, 15))
                self._add_event(session, "product_view", "product_detail", ts, target)
                for _ in range(random.randint(2, 5)):
                    ts += timedelta(seconds=random.randint(2, 8))
                    self._add_event(session, "rage_click", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(3, 10))
                self._add_event(session, "dead_click", "product_detail", ts)
                ts += timedelta(seconds=random.randint(5, 15))
                self._add_event(session, "exit", "product_detail", ts)

            elif friction == "post_purchase_anxiety":
                # Complete purchase, then generate ticket
                ts += timedelta(seconds=random.randint(15, 40))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "add_to_cart", "cart", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "checkout_start", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 50))
                self._add_event(session, "address_entry", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 40))
                self._add_event(session, "payment_attempt", "checkout", ts)
                gateway = random.choice(GATEWAYS)
                method = random.choices(PAYMENT_METHODS, weights=[30, 35, 10, 10, 10, 5])[0]
                self._payments.append({
                    "payment_id": str(uuid.uuid4()),
                    "session_id": session["session_id"],
                    "timestamp": ts,
                    "gateway": gateway,
                    "method": method,
                    "amount": round(target["price"] * random.uniform(1.0, 1.18), 2),
                    "currency": "INR",
                    "status": "success",
                    "error_code": None,
                    "latency_ms": random.randint(300, 1200),
                    "attempt_number": 1,
                })
                ts += timedelta(seconds=random.randint(2, 5))
                self._add_event(session, "order_placed", "confirmation", ts)
                order_id = f"ORD{fake.unique.random_number(digits=9)}"
                self._orders.append({
                    "order_id": order_id,
                    "session_id": session["session_id"],
                    "customer_id": session["customer_id"],
                    "product_id": target["product_id"],
                    "placed_at": ts,
                    "shipped_at": ts + timedelta(days=random.randint(2, 4)),
                    "delivered_at": None,
                    "promised_delivery": ts + timedelta(days=target["delivery_eta_days"]),
                    "status": random.choice(["delayed", "shipped"]),
                    "total_amount": round(target["price"] * 1.18, 2),
                    "payment_method": method,
                })
                # WISMO ticket
                ticket_ts = ts + timedelta(days=random.randint(3, 8))
                tmpl = random.choice(TICKET_TEMPLATES["WISMO"])
                text = tmpl.format(days=random.randint(4, 10), order_id=order_id)
                self._tickets.append({
                    "ticket_id": f"TKT{fake.unique.random_number(digits=7)}",
                    "order_id": order_id,
                    "customer_id": session["customer_id"],
                    "created_at": ticket_ts,
                    "category": "WISMO",
                    "text": _redact_pii(text),
                    "sentiment": "negative",
                    "urgency": "high",
                    "resolution_hours": round(random.uniform(2, 48), 1),
                    "reopen_count": random.choices([0, 1, 2], weights=[70, 20, 10])[0],
                })
                self._ground_truth.append({"session_id": session["session_id"], "friction_label": "post_purchase_anxiety", "is_abandoned": 0})
                continue  # skip ground truth below

            elif friction == "no_friction":
                # Smooth checkout
                ts += timedelta(seconds=random.randint(15, 40))
                self._add_event(session, "product_view", "product_detail", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "add_to_cart", "cart", ts, target)
                ts += timedelta(seconds=random.randint(10, 25))
                self._add_event(session, "checkout_start", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 50))
                self._add_event(session, "address_entry", "checkout", ts)
                ts += timedelta(seconds=random.randint(20, 40))
                self._add_event(session, "payment_attempt", "checkout", ts)
                method = random.choices(PAYMENT_METHODS, weights=[30, 35, 10, 10, 10, 5])[0]
                self._payments.append({
                    "payment_id": str(uuid.uuid4()),
                    "session_id": session["session_id"],
                    "timestamp": ts,
                    "gateway": random.choice(GATEWAYS),
                    "method": method,
                    "amount": round(target["price"] * random.uniform(1.0, 1.18), 2),
                    "currency": "INR",
                    "status": "success",
                    "error_code": None,
                    "latency_ms": random.randint(200, 800),
                    "attempt_number": 1,
                })
                ts += timedelta(seconds=random.randint(2, 5))
                self._add_event(session, "order_placed", "confirmation", ts)
                order_id = f"ORD{fake.unique.random_number(digits=9)}"
                self._orders.append({
                    "order_id": order_id,
                    "session_id": session["session_id"],
                    "customer_id": session["customer_id"],
                    "product_id": target["product_id"],
                    "placed_at": ts,
                    "shipped_at": ts + timedelta(days=random.randint(1, 3)),
                    "delivered_at": ts + timedelta(days=target["delivery_eta_days"]),
                    "promised_delivery": ts + timedelta(days=target["delivery_eta_days"]),
                    "status": "delivered",
                    "total_amount": round(target["price"] * 1.18, 2),
                    "payment_method": method,
                })
                self._ground_truth.append({"session_id": session["session_id"], "friction_label": "no_friction", "is_abandoned": 0})
                continue

            # Record ground truth for all friction (abandoned)
            self._ground_truth.append({
                "session_id": session["session_id"],
                "friction_label": friction,
                "is_abandoned": 1,
            })

    # ── Reviews ───────────────────────────────────────────────────────────────

    def _gen_reviews(self, n: int = 8000) -> None:
        print(f"  Generating {n} reviews...")
        themes = list(REVIEW_TEMPLATES.keys())
        for _ in range(n):
            theme = random.choice(themes)
            text = random.choice(REVIEW_TEMPLATES[theme])
            rating = 5 if "positive" in theme else random.choices([1, 2, 3, 4, 5], weights=[25, 20, 15, 20, 20])[0]
            pid = random.choice(self._products)["product_id"]
            self._reviews.append({
                "review_id": str(uuid.uuid4()),
                "product_id": pid,
                "customer_id": _hash_id(fake.uuid4()),
                "timestamp": fake.date_time_between(start_date="-180d", end_date="now"),
                "rating": rating,
                "text": _redact_pii(text),
                "friction_theme": theme.replace("_", " "),
            })

    # ── Extra tickets ─────────────────────────────────────────────────────────

    def _gen_extra_tickets(self, n: int = 3000) -> None:
        print(f"  Generating {n} additional support tickets...")
        categories = list(TICKET_TEMPLATES.keys())
        for _ in range(n):
            cat = random.choice(categories)
            tmpl = random.choice(TICKET_TEMPLATES[cat])
            text = tmpl.format(days=random.randint(2, 14), order_id=f"ORD{random.randint(100_000_000, 900_000_000)}")
            self._tickets.append({
                "ticket_id": f"TKT{fake.unique.random_number(digits=7)}",
                "order_id": None,
                "customer_id": _hash_id(fake.uuid4()),
                "created_at": fake.date_time_between(start_date="-90d", end_date="now"),
                "category": cat,
                "text": _redact_pii(text),
                "sentiment": random.choices(["negative", "neutral", "positive"], weights=[60, 25, 15])[0],
                "urgency": random.choices(["high", "medium", "low"], weights=[30, 45, 25])[0],
                "resolution_hours": round(random.uniform(0.5, 72), 1),
                "reopen_count": random.choices([0, 1, 2, 3], weights=[65, 20, 10, 5])[0],
            })

    # ── Recovery Responses ────────────────────────────────────────────────────

    def _gen_recovery_responses(self) -> None:
        print("  Generating recovery responses...")
        # Take ~30% of abandoned sessions and simulate interventions
        abandoned = [s for s in self._sessions if any(
            gt["session_id"] == s["session_id"] and gt["is_abandoned"] == 1
            for gt in self._ground_truth
        )]
        for session in random.sample(abandoned, min(len(abandoned), int(len(abandoned) * 0.3))):
            intervention = random.choice(INTERVENTION_CATALOG)
            channel = random.choices(["email", "sms", "push", "in_app"], weights=[40, 25, 20, 15])[0]
            converted = random.random() < random.uniform(0.05, 0.25)
            # Simulate uplift based on intervention type
            base_revenue = random.uniform(500, 5000)
            incentive_cost = base_revenue * 0.10 if "incentive" in intervention else 0.0
            self._recovery.append({
                "response_id": str(uuid.uuid4()),
                "session_id": session["session_id"],
                "customer_id": session["customer_id"],
                "sent_at": session["start_time"] + timedelta(hours=random.randint(1, 24)),
                "intervention_type": intervention,
                "channel": channel,
                "converted": converted,
                "revenue_recovered": round(base_revenue if converted else 0, 2),
                "incentive_cost": round(incentive_cost, 2),
            })

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> dict[str, Path]:
        saved = {}
        tables = {
            "products": self._products,
            "sessions": self._sessions,
            "clickstream_events": self._events,
            "payment_logs": self._payments,
            "delivery_checks": self._delivery_checks,
            "reviews": self._reviews,
            "support_tickets": self._tickets,
            "orders": self._orders,
            "recovery_responses": self._recovery,
        }
        for name, records in tables.items():
            if not records:
                print(f"  [skip] {name} - 0 records")
                continue
            path = self.output_dir / f"{name}.parquet"
            pd.DataFrame(records).to_parquet(path, index=False)
            print(f"  Saved {len(records):,} rows -> {path}")
            saved[name] = path

        # Ground truth – separate file
        gt_path = self.output_dir / "ground_truth_labels.parquet"
        pd.DataFrame(self._ground_truth).to_parquet(gt_path, index=False)
        print(f"  Saved {len(self._ground_truth):,} rows -> {gt_path} (ground truth, NOT used in inference)")
        saved["ground_truth"] = gt_path

        return saved

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> dict[str, Path]:
        print("=" * 60)
        print(f"FrictionIQ Synthetic Data Generator  (seed={self.seed})")
        print(f"Target sessions: {self.n_sessions:,}")
        print("=" * 60)
        self._gen_products()
        self._gen_sessions()
        self._gen_events()
        self._gen_reviews()
        self._gen_extra_tickets()
        self._gen_recovery_responses()
        paths = self._save()
        print("=" * 60)
        print("Data generation complete.")
        return paths


if __name__ == "__main__":
    gen = SyntheticGenerator(n_sessions=50_000, seed=42, output_dir="data/processed")
    gen.run()
