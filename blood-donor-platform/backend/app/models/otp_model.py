"""
OTP document model, used for mandatory email verification during:
  - registration (purpose="registration")
  - blood request submission, when the request email differs from the
    logged-in user's verified email (purpose="blood_request")

A TTL index on `expires_at` (see core/database.py) automatically deletes
expired OTP documents, so there is no need for a manual cleanup job.
"""
import datetime as dt
import enum
from typing import Any

from app.core.config import settings


class OtpPurpose(str, enum.Enum):
    REGISTRATION = "registration"
    BLOOD_REQUEST = "blood_request"


def build_otp_document(*, email: str, otp_hash: str, purpose: OtpPurpose) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "email": email.lower().strip(),
        "otp_hash": otp_hash,
        "purpose": purpose.value,
        "attempts": 0,
        "verified": False,
        "created_at": now,
        "expires_at": now + dt.timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    }
