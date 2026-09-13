from typing import Optional

from pydantic import BaseModel

from app.models.user_model import BloodGroup, Role
from app.schemas.common_schema import AddressSchema


class UserProfileResponse(BaseModel):
    id: str
    role: Role
    first_name: str
    last_name: str
    age: int
    blood_group: BloodGroup
    contact: str
    email: str
    address: AddressSchema
    location_sharing_permission: bool
    is_email_verified: bool
    is_active: bool
    created_at: str


class AuthResponse(BaseModel):
    """Returned by both /auth/register and /auth/login -- registration auto-logs-in the user."""
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class NearbyDonorResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    blood_group: BloodGroup
    city_town: str
    distance_km: Optional[float] = None
