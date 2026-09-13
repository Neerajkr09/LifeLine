"""
Central configuration module.

All environment-driven settings live here. Nothing else in the codebase should
call os.environ / os.getenv directly -- import `settings` from this module
instead. This keeps configuration in one auditable place and makes it easy to
add new settings without touching business logic.
"""
from functools import lru_cache
from typing import List

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "Blood Donor-Recipient Connection Platform API"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ---- Security / JWT ----
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_super_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ---- MongoDB Atlas ----
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "blood_donor_platform"

    # ---- CORS ----
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- OTP / Email verification ----
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6
    OTP_MAX_ATTEMPTS: int = 5

    # ---- SMTP (optional -- falls back to console logging when unset) ----
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: EmailStr = "no-reply@example.com"
    SMTP_USE_TLS: bool = True

    # ---- File uploads ----
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_UPLOAD_CONTENT_TYPES: str = "application/pdf,image/jpeg,image/png,image/jpg"

    # ---- Rate limiting ----
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_OTP: str = "5/minute"

    # ---- Fraud detection ----
    # If a single blood request accumulates this many donor rejections, the
    # recipient account is auto-banned and the request is cancelled, on the
    # theory that a genuine request is unlikely to be turned down by this
    # many independent, blood-group-compatible donors in a row.
    DONOR_REJECTION_BAN_THRESHOLD: int = 5

    # ---- Community outreach (OSM harvest + contact scrape) ----
    # When a request is created, its location is handed off to osmharvest
    # (a sibling project) to find nearby colleges/universities/restaurants/
    # pubs that might help spread the word or host a donation drive. This
    # backend only *submits* the job (a fast local sqlite insert, no
    # network call) -- the actual Overpass fetching and website scraping run
    # in separate long-lived worker processes. See outreach_orchestrator/.
    OUTREACH_ENABLED: bool = True
    OUTREACH_RADIUS_METRES: float = 5000.0
    OUTREACH_CATEGORIES: str = "college,university,restaurant,pub"
    # Path to the osmharvest sqlite database. Must match --db / OsmProject's
    # default so this backend and the osmharvest worker agree on where jobs
    # live.
    OSM_DB_PATH: str = "../../OsmProject/osmharvest.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_upload_types_list(self) -> List[str]:
        return [t.strip() for t in self.ALLOWED_UPLOAD_CONTENT_TYPES.split(",") if t.strip()]

    @property
    def outreach_categories_list(self) -> List[str]:
        return [c.strip() for c in self.OUTREACH_CATEGORIES.split(",") if c.strip()]

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor -- .env is read once per process."""
    return Settings()


settings = get_settings()
