import datetime as dt
import secrets

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.controllers.email_controller import send_otp_email
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.otp_model import OtpPurpose, build_otp_document
from app.models.user_model import build_user_document
from app.schemas.auth_schema import LoginRequest, RegisterRequest, SendOtpRequest, VerifyOtpRequest
from app.utils.serializers import serialize_user


async def send_otp(db: AsyncIOMotorDatabase, payload: SendOtpRequest) -> None:
    otp = "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))
    otp_hash = hash_password(otp)  # bcrypt-hash the OTP at rest, same as passwords

    # Invalidate any previous outstanding OTPs for this email+purpose so only
    # the most recently issued code is valid.
    await db.otps.delete_many({"email": payload.email.lower(), "purpose": payload.purpose})

    doc = build_otp_document(email=payload.email, otp_hash=otp_hash, purpose=OtpPurpose(payload.purpose))
    await db.otps.insert_one(doc)

    send_otp_email(payload.email, otp, payload.purpose)


async def verify_otp(db: AsyncIOMotorDatabase, payload: VerifyOtpRequest) -> None:
    otp_doc = await db.otps.find_one({"email": payload.email.lower(), "purpose": payload.purpose})
    if otp_doc is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No verification code was requested for this email.")

    if otp_doc.get("verified"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This verification code has already been used.")

    if otp_doc["expires_at"].replace(tzinfo=dt.timezone.utc) < dt.datetime.now(dt.timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification code has expired. Please request a new one.")

    if otp_doc["attempts"] >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many incorrect attempts. Request a new code.")

    if not verify_password(payload.otp, otp_doc["otp_hash"]):
        await db.otps.update_one({"_id": otp_doc["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect verification code.")

    await db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"verified": True}})


async def consume_verified_otp(db: AsyncIOMotorDatabase, email: str, purpose: str) -> None:
    """Ensures email verification actually happened server-side, then burns the OTP."""
    otp_doc = await db.otps.find_one({"email": email.lower(), "purpose": purpose, "verified": True})
    if otp_doc is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Email has not been verified. Please verify your email with the code sent to it first.",
        )
    if otp_doc["expires_at"].replace(tzinfo=dt.timezone.utc) < dt.datetime.now(dt.timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email verification has expired. Please verify again.")
    await db.otps.delete_one({"_id": otp_doc["_id"]})


async def register_user(db: AsyncIOMotorDatabase, payload: RegisterRequest) -> tuple[str, dict]:
    await consume_verified_otp(db, payload.email, "registration")

    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    doc = build_user_document(
        first_name=payload.first_name,
        last_name=payload.last_name,
        age=payload.age,
        blood_group=payload.blood_group.value,
        contact=payload.contact,
        email=payload.email,
        address=payload.address.model_dump(),
        location_sharing_permission=payload.location_sharing_permission,
        location=payload.location.to_geojson() if payload.location else None,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    token = create_access_token(subject=str(doc["_id"]), role=doc["role"])
    return token, serialize_user(doc)


async def login_user(db: AsyncIOMotorDatabase, payload: LoginRequest) -> tuple[str, dict]:
    user = await db.users.find_one({"email": payload.email.lower(), "is_deleted": False})
    if user is None or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if user.get("is_banned"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ACCOUNT IS BANNED DUE TO SUSPECTED ACTIVITY!")
    if not user.get("is_active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated.")

    token = create_access_token(subject=str(user["_id"]), role=user["role"])
    return token, serialize_user(user)
