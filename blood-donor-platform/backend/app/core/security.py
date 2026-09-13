"""
Security primitives: password hashing and JWT issuance/verification.

Password hashing uses the `bcrypt` library directly (rather than passlib)
to avoid the well-known passlib <-> bcrypt>=4.1 version-compatibility issues,
and because bcrypt alone is all that's needed here.
"""
import datetime as dt
from typing import Any

import bcrypt
import jwt
from jwt import PyJWTError

from app.core.config import settings

ALGORITHM = settings.JWT_ALGORITHM


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, role: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    expire = now + dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and verifies a JWT. Raises jwt.PyJWTError subclasses on failure
    (ExpiredSignatureError, InvalidTokenError, etc) -- callers should catch
    PyJWTError and translate to an HTTP 401.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "PyJWTError",
]
