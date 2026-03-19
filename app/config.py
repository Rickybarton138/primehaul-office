"""
Centralized configuration for PrimeHaul Office Manager.
All environment variables loaded and validated here.
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # --- Required ---
        self.DATABASE_URL: str = self._require("DATABASE_URL")
        self.JWT_SECRET_KEY: str = self._require("JWT_SECRET_KEY")
        self.ADMIN_PASSWORD: str = self._require("ADMIN_PASSWORD")

        # --- App ---
        self.APP_URL: str = os.getenv("APP_URL", "https://office.primehaul.co.uk")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.RAILWAY_PUBLIC_DOMAIN: str = os.getenv("RAILWAY_PUBLIC_DOMAIN", "localhost:8000")

        # --- Stripe ---
        self.STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
        self.STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")

        # --- SMTP ---
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@primehaul.co.uk")
        self.SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "PrimeHaul Office")

        # --- OpenAI ---
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_VISION_MODEL: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

        # --- Social Media ---
        self.META_PAGE_ACCESS_TOKEN: str = os.getenv("META_PAGE_ACCESS_TOKEN", "")
        self.META_PAGE_ID: str = os.getenv("META_PAGE_ID", "")
        self.META_INSTAGRAM_ACCOUNT_ID: str = os.getenv("META_INSTAGRAM_ACCOUNT_ID", "")
        self.X_API_KEY: str = os.getenv("X_API_KEY", "")
        self.X_API_SECRET: str = os.getenv("X_API_SECRET", "")
        self.X_ACCESS_TOKEN: str = os.getenv("X_ACCESS_TOKEN", "")
        self.X_ACCESS_TOKEN_SECRET: str = os.getenv("X_ACCESS_TOKEN_SECRET", "")
        self.SOCIAL_AUTO_PUBLISH: bool = os.getenv("SOCIAL_AUTO_PUBLISH", "true").lower() == "true"
        self.SOCIAL_POSTS_PER_DAY: int = int(os.getenv("SOCIAL_POSTS_PER_DAY", "2"))

        # --- Mapbox ---
        self.MAPBOX_ACCESS_TOKEN: str = os.getenv("MAPBOX_ACCESS_TOKEN", "")

        # --- Lead Ingestion API Keys ---
        self.LEAD_API_KEY: str = os.getenv("LEAD_API_KEY", "")

    def _require(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            logger.critical(f"FATAL: Required environment variable {key} is not set. Exiting.")
            sys.exit(1)
        return value


settings = Settings()
