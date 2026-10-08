"""
FrictionIQ – JWT Security & Role-Based Access Control
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

ROLES = ["admin", "marketing", "product", "customer_service", "operations"]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["*"],
    "marketing": ["read:kpis", "read:funnel", "read:segments", "read:recommendations", "trigger:email", "trigger:sms"],
    "product": ["read:kpis", "read:funnel", "read:friction", "read:sessions", "read:feedback"],
    "customer_service": ["read:sessions", "read:tickets", "trigger:support", "read:responses"],
    "operations": ["read:kpis", "read:delivery", "read:anomalies", "read:audit"],
}

# Demo users for development (never use in production – load from DB)
DEMO_USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "marketer": {"password": "mark123", "role": "marketing"},
    "product_mgr": {"password": "prod123", "role": "product"},
    "cs_agent": {"password": "cs123", "role": "customer_service"},
    "ops_lead": {"password": "ops123", "role": "operations"},
}


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict[str, Any]:
    if not credentials:
        # Dev mode: return demo admin
        if get_settings().ENV == "development":
            return {"sub": "admin", "role": "admin"}
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    return payload


def require_role(allowed_roles: list[str]):
    async def dependency(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles and "admin" not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        if user.get("role") not in allowed_roles and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
