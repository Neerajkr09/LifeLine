from typing import Annotated

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.controllers import auth_controller
from app.core.config import settings
from app.core.database import get_database
from app.middleware.rate_limiter import limiter
from app.schemas.auth_schema import LoginRequest, RegisterRequest, SendOtpRequest, VerifyOtpRequest
from app.schemas.common_schema import MessageResponse
from app.schemas.user_schema import AuthResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/send-otp", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_OTP)
async def send_otp(
    request: Request,
    payload: SendOtpRequest,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    await auth_controller.send_otp(db, payload)
    return MessageResponse(message=f"A verification code has been sent to {payload.email}.")


@router.post("/verify-otp", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_OTP)
async def verify_otp(
    request: Request,
    payload: VerifyOtpRequest,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    await auth_controller.verify_otp(db, payload)
    return MessageResponse(message="Email verified successfully.")


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    """Registration auto-logs-in the new user (returns a token), per spec:
    'After successful registration redirect user to respective dashboard'."""
    token, profile = await auth_controller.register_user(db, payload)
    return AuthResponse(access_token=token, user=profile)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
):
    token, profile = await auth_controller.login_user(db, payload)
    return AuthResponse(access_token=token, user=profile)
