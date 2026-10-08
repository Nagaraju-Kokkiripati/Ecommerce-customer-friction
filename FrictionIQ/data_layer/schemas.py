"""
FrictionIQ – Canonical data schemas for the unified data layer.
All loaders (public datasets + synthetic) map into these schemas.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    event_id: str
    session_id: str
    customer_id: str           # salted-hash anonymized
    timestamp: datetime
    event_type: str            # page_view, search, product_view, compare, add_to_cart,
                               # remove_from_cart, checkout_start, address_entry,
                               # delivery_check, payment_attempt, payment_fail,
                               # order_placed, exit, rage_click, dead_click
    page: Optional[str] = None
    product_id: Optional[str] = None
    query: Optional[str] = None
    device: str = "unknown"    # mobile, desktop, tablet
    channel: str = "unknown"   # organic, paid_search, social, email, direct
    country: str = "IN"
    extra: dict = field(default_factory=dict)


@dataclass
class Session:
    session_id: str
    customer_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    device: str = "unknown"
    channel: str = "unknown"
    country: str = "IN"
    is_new_customer: bool = True
    friction_label: Optional[str] = None   # ground truth, kept separate


@dataclass
class PaymentLog:
    payment_id: str
    session_id: str
    timestamp: datetime
    gateway: str
    method: str                # card, upi, netbanking, wallet, cod, bnpl
    amount: float
    currency: str = "INR"
    status: str = "success"    # success, failed, pending
    error_code: Optional[str] = None   # 3DS_TIMEOUT, INSUFFICIENT_FUNDS, BANK_DECLINE, ...
    latency_ms: Optional[int] = None
    attempt_number: int = 1


@dataclass
class DeliveryCheck:
    check_id: str
    session_id: str
    product_id: str
    timestamp: datetime
    pincode: str
    promised_eta_days: int
    is_serviceable: bool
    shipping_fee: float
    actual_eta_days: Optional[int] = None   # filled post-order from Olist-style data


@dataclass
class Product:
    product_id: str
    category: str
    subcategory: Optional[str] = None
    price: float = 0.0
    description_quality_score: float = 0.5   # 0-1
    image_count: int = 0
    stock: int = 100
    delivery_eta_days: int = 5
    return_policy: str = "30_days"
    rating: float = 4.0
    review_count: int = 0
    seller_id: Optional[str] = None


@dataclass
class Review:
    review_id: str
    product_id: str
    customer_id: str
    timestamp: datetime
    rating: int
    text: str
    sentiment: Optional[str] = None   # positive, neutral, negative
    friction_theme: Optional[str] = None


@dataclass
class SupportTicket:
    ticket_id: str
    order_id: Optional[str]
    customer_id: str
    created_at: datetime
    category: str    # WISMO, payment, return, product_info, delivery, other
    text: str
    sentiment: Optional[str] = None
    urgency: Optional[str] = None
    resolution_hours: Optional[float] = None
    reopen_count: int = 0


@dataclass
class Order:
    order_id: str
    session_id: Optional[str]
    customer_id: str
    product_id: str
    placed_at: datetime
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    promised_delivery: Optional[datetime] = None
    status: str = "placed"   # placed, shipped, delayed, delivered, returned, refunded
    total_amount: float = 0.0
    payment_method: Optional[str] = None


@dataclass
class RecoveryResponse:
    response_id: str
    session_id: str
    customer_id: str
    sent_at: datetime
    intervention_type: str
    channel: str           # email, sms, push, in_app
    converted: bool = False
    revenue_recovered: float = 0.0
    incentive_cost: float = 0.0
