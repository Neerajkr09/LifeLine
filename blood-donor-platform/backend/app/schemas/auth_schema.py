from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.user_model import BloodGroup, Role
from app.schemas.common_schema import AddressSchema, GeoLocationSchema
from app.utils.validators import validate_contact_number, validate_human_name, validate_strong_password


class RegisterRequest(BaseModel):
    """
    Note: this schema intentionally has no `otp` field. Email verification is
    a two-step flow completed *before* this call:
      1. POST /auth/send-otp        -> OTP emailed, stored hashed w/ verified=False
      2. POST /auth/verify-otp      -> marks that OTP document verified=True
    The register endpoint's controller checks for a verified, unexpired OTP
    document matching this email + purpose="registration" server-side, and
    consumes (deletes) it on success. This is what "Register button remains
    disabled until email verification is successful" gates on the frontend,
    and what the backend independently re-validates so the check can't be
    bypassed by calling the API directly.
    """

    role: Role
    first_name: str = Field(..., max_length=80)
    last_name: str = Field(..., max_length=80)
    age: int = Field(..., ge=18, le=100, description="Donors/recipients must be 18-100 years old")
    blood_group: BloodGroup
    contact: str
    email: EmailStr
    address: AddressSchema
    location_sharing_permission: bool
    location: Optional[GeoLocationSchema] = None
    password: str
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_names(cls, v: str) -> str:
        return validate_human_name(v)

    @field_validator("contact")
    @classmethod
    def _validate_contact(cls, v: str) -> str:
        return validate_contact_number(v)

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, v: str) -> str:
        return validate_strong_password(v)

    @model_validator(mode="after")
    def _validate_matching_passwords_and_location(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and Confirm Password must match.")
        if not self.location_sharing_permission:
            raise ValueError("Location sharing permission is mandatory.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SendOtpRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(default="registration", pattern="^(registration|blood_request)$")


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=8)
    purpose: str = Field(default="registration", pattern="^(registration|blood_request)$")
