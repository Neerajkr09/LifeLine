"""
User document model.

Design decision: Donors and Recipients share an almost identical set of
fields (name, age, blood group, contact, address, location, credentials), so
they live in a single `users` collection discriminated by a `role` field
rather than two separate collections. This keeps the schema normalized (no
duplicated field definitions), lets a single auth/login flow serve both
roles, and still leaves room to bolt on role-specific fields later (e.g. a
donor's `last_donated_at`) without a migration -- Mongo documents are not
rigid, and role-specific fields are simply absent on the other role's docs.

Mongo is schema-less, so these classes are not an ODM layer; they exist to
give the rest of the codebase a single, typed source of truth for what a
user document looks like and how to build one.
"""
import datetime as dt
import enum
from typing import Any, Optional, TypedDict


class Role(str, enum.Enum):
    DONOR = "donor"
    RECIPIENT = "recipient"


class BloodGroup(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class Address(TypedDict, total=False):
    address_line: str
    postcode: str
    city_town: str


class GeoPoint(TypedDict, total=False):
    type: str  # always "Point"
    coordinates: list[float]  # [longitude, latitude]


def build_user_document(
    *,
    first_name: str,
    last_name: str,
    age: int,
    blood_group: str,
    contact: str,
    email: str,
    address: Address,
    location_sharing_permission: bool,
    location: Optional[GeoPoint],
    hashed_password: str,
    role: Role,
) -> dict[str, Any]:
    """Builds a brand-new user document ready for insertion."""
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "first_name": first_name,
        "last_name": last_name,
        "age": age,
        "blood_group": blood_group,
        "contact": contact,
        "email": email.lower().strip(),
        "address": dict(address),
        "location_sharing_permission": location_sharing_permission,
        "location": dict(location) if location else None,
        "hashed_password": hashed_password,
        "role": role.value,
        "is_email_verified": True,  # verified prior to registration via OTP flow
        "is_active": True,
        "is_deleted": False,
        "is_banned": False,
        "created_at": now,
        "updated_at": now,
    }


PUBLIC_USER_PROJECTION = {
    "hashed_password": 0,
}
