"""
FrictionIQ – Core Settings
All config loaded from environment variables / .env file.
No hardcoded secrets.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "FrictionIQ"
    APP_VERSION: str = "2.0.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""
    ABANDONMENT_MINUTES: int = Field(default=30, ge=1)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    EMAIL_MODE: Literal["simulated", "smtp"] = "simulated"
    LOG_LEVEL: str = "INFO"

    # ── Paths ─────────────────────────────────────────────────────────────────
    DATA_DIR: Path = ROOT / "data"
    RAW_DIR: Path = ROOT / "data" / "raw"
    PROCESSED_DIR: Path = ROOT / "data" / "processed"
    FEATURE_STORE_DIR: Path = ROOT / "data" / "feature_store"
    MODEL_REGISTRY_DIR: Path = ROOT / "models" / "registry"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite+aiosqlite:///{ROOT}/data/frictioniq.db"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_256BIT_KEY"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── LLM Provider ─────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["gemini", "openai", "anthropic", "deepseek", "qwen", "mock"] = "mock"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_TEMPERATURE: float = 0.2

    # ── Data Generation ───────────────────────────────────────────────────────
    SYNTHETIC_SESSIONS: int = 50_000
    SYNTHETIC_SEED: int = 42

    # ── ML ────────────────────────────────────────────────────────────────────
    TRAIN_TEST_SPLIT: float = 0.2
    CALIBRATE_MODELS: bool = True

    # ── Business Rules / Guardrails ───────────────────────────────────────────
    MAX_DISCOUNT_PCT: float = 20.0
    MIN_MARGIN_PCT: float = 15.0
    HIGH_IMPACT_REQUIRES_APPROVAL: bool = True

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000", "http://localhost:3000"]

    def ensure_dirs(self) -> None:
        for p in [self.DATA_DIR, self.RAW_DIR, self.PROCESSED_DIR,
                  self.FEATURE_STORE_DIR, self.MODEL_REGISTRY_DIR]:
            p.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    if s.ENV != "development":
        if s.SECRET_KEY == "CHANGE_ME_IN_PRODUCTION_USE_256BIT_KEY" or len(s.SECRET_KEY) < 32:
            raise ValueError("Configure a random SECRET_KEY of at least 32 characters")
        if not s.ADMIN_PASSWORD_HASH:
            raise ValueError("Configure ADMIN_PASSWORD_HASH outside development")
    s.ensure_dirs()
    return s
