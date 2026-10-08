"""Persistent prototype storefront and observed customer journeys (SQLite)."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Literal

from core.config import get_settings
from core.security import create_access_token, decode_token, get_current_user

router = APIRouter()

PRODUCTS = [
    {"id": "p1", "name": "Everyday Headphones", "category": "Electronics", "price": 2499, "description": "Wireless over-ear headphones, 30-hour battery, USB-C charging. Includes a one-year warranty.", "art": "headphones", "color": "#e9ddff"},
    {"id": "p2", "name": "Weekend Backpack", "category": "Accessories", "price": 1899, "description": "Water-resistant 20L backpack with a padded 14-inch laptop sleeve and adjustable straps.", "art": "backpack", "color": "#d9eee7"},
    {"id": "p3", "name": "Studio Desk Lamp", "category": "Home", "price": 1299, "description": "Adjustable LED desk lamp with three brightness settings. USB cable included.", "art": "lamp", "color": "#ffe8ca"},
    {"id": "p4", "name": "Daily Ceramic Mug", "category": "Home", "price": 499, "description": "350ml ceramic mug. Dishwasher safe; available in a soft cream finish.", "art": "mug", "color": "#f4dce4"},
    {"id": "p5", "name": "Classic Canvas Sneakers", "category": "Fashion", "price": 1599, "description": "Breathable canvas upper and rubber sole. Unisex UK size 7. Check your size before ordering.", "art": "shoe", "color": "#dbe8ff"},
    {"id": "p6", "name": "Pocket Notebook", "category": "Accessories", "price": 299, "description": "A5 hardcover notebook with 160 dotted pages and a ribbon bookmark.", "art": "book", "color": "#e8e8d5"},
]


def now():
    return datetime.now(timezone.utc).isoformat()


def database():
    path = get_settings().DATA_DIR / "storefront.sqlite3"
    with closing(sqlite3.connect(path, timeout=15)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript('''
            CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, password TEXT, consent INTEGER);
            CREATE TABLE IF NOT EXISTS journeys (id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id), created TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, session_id TEXT REFERENCES journeys(id), type TEXT, timestamp TEXT, details TEXT);
            CREATE TABLE IF NOT EXISTS carts (customer_id TEXT, product_id TEXT, quantity INTEGER, PRIMARY KEY(customer_id, product_id));
            CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer_id TEXT, session_id TEXT, total INTEGER, items TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS recoveries (id TEXT PRIMARY KEY, session_id TEXT, message TEXT, channel TEXT, created TEXT);
        ''')
        yield db


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ":" + value


def customer(request: Request, db=Depends(database)):
    token = request.cookies.get("shop_token")
    if not token:
        raise HTTPException(401, "Please sign in")
    claims = decode_token(token)
    if claims.get("role") != "customer":
        raise HTTPException(403, "Customer account required")
    row = db.execute("SELECT * FROM customers WHERE id=?", (claims.get("sub"),)).fetchone()
    journey = db.execute("SELECT id FROM journeys WHERE id=? AND customer_id=?", (claims.get("session_id"), claims.get("sub"))).fetchone()
    if not row or not journey:
        raise HTTPException(401, "Session unavailable; sign in again")
    return dict(row) | {"session_id": journey["id"]}


def admin(request: Request, user=Depends(get_current_user)):
    # Captured customer journeys always require an explicit administrator token.
    if not request.headers.get("authorization") or user.get("role") != "admin":
        raise HTTPException(403, "Sign in as an administrator to view captured journeys")
    return user


def event(db, sid, kind, details=None):
    db.execute("INSERT INTO events(session_id,type,timestamp,details) VALUES(?,?,?,?)", (sid, kind, now(), json.dumps(details or {})))


class Signup(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    consent: bool = False


class Login(BaseModel):
    email: str
    password: str = Field(max_length=128)


def start_session(row, response, db):
    sid = "shop_" + uuid.uuid4().hex
    db.execute("INSERT INTO journeys VALUES(?,?,?)", (sid, row["id"], now()))
    event(db, sid, "session_start")
    response.set_cookie("shop_token", create_access_token({"sub": row["id"], "role": "customer", "session_id": sid}), httponly=True, samesite="strict", secure=get_settings().ENV != "development", max_age=3600)
    return {"name": row["name"], "session_id": sid, "consent": bool(row["consent"])}


@router.post("/api/shop/signup")
def signup(body: Signup, response: Response, db=Depends(database)):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or not body.name.strip():
        raise HTTPException(422, "Enter a valid name and email")
    row = {"id": uuid.uuid4().hex, "email": email, "name": body.name.strip(), "password": password_hash(body.password), "consent": int(body.consent)}
    try:
        db.execute("INSERT INTO customers VALUES(:id,:email,:name,:password,:consent)", row)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This email is already registered")
    return start_session(row, response, db)


@router.post("/api/shop/login")
def login(body: Login, response: Response, db=Depends(database)):
    row = db.execute("SELECT * FROM customers WHERE email=?", (body.email.strip().lower(),)).fetchone()
    # Perform the same expensive hash on unknown accounts.
    stored = row["password"] if row else password_hash("dummy-password")
    if not hmac.compare_digest(password_hash(body.password, stored.split(":")[0]), stored) or not row:
        raise HTTPException(401, "Invalid email or password")
    return start_session(row, response, db)


@router.post("/api/shop/logout")
def logout(response: Response):
    response.delete_cookie("shop_token")
    return {"status": "signed_out"}


@router.get("/api/shop/me")
def me(user=Depends(customer)):
    return {"name": user["name"], "session_id": user["session_id"], "consent": bool(user["consent"])}


@router.get("/api/shop/products")
def products():
    return PRODUCTS


class Event(BaseModel):
    type: Literal["product_view", "search", "search_no_results", "checkout_start", "product_compare"]
    product_id: str | None = None
    query: str = Field(default="", max_length=120)


@router.post("/api/shop/events")
def track(body: Event, user=Depends(customer), db=Depends(database)):
    if body.product_id and body.product_id not in {p["id"] for p in PRODUCTS}:
        raise HTTPException(404, "Product not found")
    event(db, user["session_id"], body.type, body.model_dump(exclude_none=True))
    return {"recorded": True}


def cart_data(db, uid):
    rows = db.execute("SELECT * FROM carts WHERE customer_id=?", (uid,)).fetchall()
    catalog = {p["id"]: p for p in PRODUCTS}
    items = [catalog[r["product_id"]] | {"quantity": r["quantity"]} for r in rows]
    return {"items": items, "total": sum(p["price"] * p["quantity"] for p in items)}


@router.get("/api/shop/cart")
def cart(user=Depends(customer), db=Depends(database)):
    return cart_data(db, user["id"])


class CartUpdate(BaseModel):
    product_id: str
    quantity: int = Field(ge=0, le=20)


@router.put("/api/shop/cart")
def update_cart(body: CartUpdate, user=Depends(customer), db=Depends(database)):
    if body.product_id not in {p["id"] for p in PRODUCTS}:
        raise HTTPException(404, "Product not found")
    old = db.execute("SELECT quantity FROM carts WHERE customer_id=? AND product_id=?", (user["id"], body.product_id)).fetchone()
    previous = old[0] if old else 0
    if body.quantity:
        db.execute("INSERT OR REPLACE INTO carts VALUES(?,?,?)", (user["id"], body.product_id, body.quantity))
    else:
        db.execute("DELETE FROM carts WHERE customer_id=? AND product_id=?", (user["id"], body.product_id))
    event(db, user["session_id"], "add_to_cart" if body.quantity > previous else "remove_from_cart", {"product_id": body.product_id, "quantity": body.quantity})
    return cart_data(db, user["id"])


class Payment(BaseModel):
    outcome: Literal["success", "failure", "cancelled"]
    delivery_address: str = Field(min_length=10, max_length=500)
    method: Literal["demo_card", "demo_wallet"] = "demo_card"


@router.post("/api/shop/payment")
def payment(body: Payment, user=Depends(customer), db=Depends(database)):
    cart = cart_data(db, user["id"])
    if not cart["items"]:
        raise HTTPException(409, "Your cart is empty")
    if len(body.delivery_address.strip()) < 10:
        raise HTTPException(422, "Enter a complete delivery address")
    # Demo address is validated but not stored; no card data is collected.
    event(db, user["session_id"], "payment_attempt", {"method": body.method})
    event(db, user["session_id"], "payment_" + body.outcome, {"method": body.method, "total": cart["total"]})
    order_id = None
    if body.outcome == "success":
        order_id = "ORD-" + uuid.uuid4().hex[:10].upper()
        db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)", (order_id, user["id"], user["session_id"], cart["total"], json.dumps(cart["items"]), now()))
        event(db, user["session_id"], "order_placed", {"order_id": order_id, "total": cart["total"]})
        db.execute("DELETE FROM carts WHERE customer_id=?", (user["id"],))
    return {"outcome": body.outcome, "order_id": order_id, "simulated": True}


@router.get("/api/shop/orders")
def orders(user=Depends(customer), db=Depends(database)):
    return [dict(r) | {"items": json.loads(r["items"]), "status": "Confirmed (demo)"} for r in db.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY created DESC", (user["id"],))]


def journey_detail(db, sid):
    row = db.execute("SELECT j.*,c.name,c.consent FROM journeys j JOIN customers c ON c.id=j.customer_id WHERE j.id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Captured session not found")
    events = [dict(e) | {"details": json.loads(e["details"])} for e in db.execute("SELECT * FROM events WHERE session_id=? ORDER BY id", (sid,))]
    counts = {}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    failures = counts.get("payment_failure", 0)
    completed = bool(counts.get("order_placed"))
    no_results = counts.get("search_no_results", 0)
    score = 0 if completed else min(95, failures * 35 + no_results * 15 + (15 if counts.get("checkout_start") else 0))
    facts = [f"{failures} simulated payment failures", f"{counts.get('product_view', 0)} product views", f"{no_results} searches with no results", "Order placed" if completed else "No order placed in this session"]
    inference = "Purchase completed; earlier friction was resolved." if completed else "Payment difficulties may prevent completion." if failures else "The customer may need help finding products." if no_results else "No strong friction signal yet; an unfinished session is not proof of abandonment."
    recommendation = "No intervention needed" if completed else "Offer an alternative demo payment method" if failures else "Help refine the search" if no_results else "Continue monitoring"
    recovery = [dict(r) for r in db.execute("SELECT * FROM recoveries WHERE session_id=? ORDER BY created", (sid,))]
    recovered = False
    for action in recovery:
        if db.execute("SELECT 1 FROM orders WHERE customer_id=? AND created>? LIMIT 1", (row["customer_id"], action["created"])).fetchone():
            recovered = True
    return {"session_id": sid, "name": row["name"], "created": row["created"], "consent": bool(row["consent"]), "events": events, "facts": facts, "inference": inference, "recommendation": recommendation, "risk_score": score, "model": "observed_event_rules", "completed": completed, "recoveries": recovery, "recovery_outcome": "purchase_after_simulated_action" if recovered else "awaiting_purchase" if recovery else "no_action"}


@router.get("/api/journeys", dependencies=[Depends(admin)])
def journeys(db=Depends(database)):
    return [journey_detail(db, r[0]) for r in db.execute("SELECT id FROM journeys ORDER BY created DESC LIMIT 100").fetchall()]


@router.get("/api/journeys/{sid}", dependencies=[Depends(admin)])
def journey(sid: str, db=Depends(database)):
    return journey_detail(db, sid)


class Recovery(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/api/journeys/{sid}/recovery", dependencies=[Depends(admin)])
def recovery(sid: str, body: Recovery, db=Depends(database)):
    detail = journey_detail(db, sid)
    if not detail["consent"]:
        raise HTTPException(409, "Customer has not opted into recovery emails")
    if detail["completed"]:
        raise HTTPException(409, "This session has already converted")
    rid = "REC-" + uuid.uuid4().hex[:10]
    db.execute("INSERT INTO recoveries VALUES(?,?,?,?,?)", (rid, sid, body.message, "email_simulation", now()))
    return {"id": rid, "status": "simulated", "message": "Recovery recorded; no email was delivered"}
