from typing import Optional

from pydantic import BaseModel, EmailStr, Field, PrivateAttr, ValidationError, field_validator, model_validator

from app.models.blood_request_model import RequestStatus
from app.models.user_model import BloodGroup
from app.schemas.common_schema import AddressSchema, GeoLocationSchema
from app.utils.validators import validate_contact_number, validate_human_name

# NOTE: the actual HTTP endpoint receives these fields as multipart Form
# fields (because a file upload is mandatory alongside them), not as a JSON
# body. This model is instantiated manually in the route from the parsed
# Form() values so we still get full Pydantic validation in one place.
#
# Patient-identity fields (name/age/blood group/contact/email/address) are
# declared as raw, unvalidated Optional strings here -- NOT because they're
# optional in general, but because their validity depends on for_self vs.
# for_other:
#   - for_self=True:  the server overwrites these from the logged-in user's
#                      own profile (see blood_request_controller), so
#                      whatever the client sent is discarded and need not
#                      be well-formed.
#   - for_other=True:  these describe a third party and must be fully valid,
#                      which the `_validate_patient_fields` validator below
#                      enforces by re-running them through the same
#                      field-level validators/schemas used at registration.


class BloodRequestCreate(BaseModel):
    for_self: bool
    for_other: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    blood_group: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    address_line: Optional[str] = None
    postcode: Optional[str] = None
    city_town: Optional[str] = None
    location: GeoLocationSchema
    accepted_warning: bool = Field(
        ...,
        description=(
            "Must be true. Confirms the user was shown and accepted the "
            "'submitted requests can never be edited, fake documents = permanent ban' warning."
        ),
    )
    _validated_patient: dict = PrivateAttr(default_factory=dict)

    @field_validator("accepted_warning")
    @classmethod
    def _must_accept_warning(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must acknowledge the warning before submitting a request.")
        return v

    @model_validator(mode="after")
    def _validate_self_xor_other(self) -> "BloodRequestCreate":
        if self.for_self == self.for_other:
            raise ValueError(
                "Exactly one of 'Blood Requirement For Self' or 'Blood Requirement For Other' "
                "must be selected."
            )
        if self.for_other:
            self._validated_patient = _validate_other_patient_fields(self)
        return self

    def other_patient_fields(self) -> dict:
        """Only meaningful when for_other=True; validated & normalized fields for a third party."""
        return self._validated_patient


def _validate_other_patient_fields(model: "BloodRequestCreate") -> dict:
    errors: list[str] = []
    result: dict = {}

    for field_name, validator in (("first_name", validate_human_name), ("last_name", validate_human_name)):
        raw = getattr(model, field_name) or ""
        try:
            result[field_name] = validator(raw)
        except ValueError as exc:
            errors.append(f"{field_name}: {exc}")

    if model.age is None or not (0 <= model.age <= 120):
        errors.append("age: must be between 0 and 120.")
    else:
        result["age"] = model.age

    try:
        result["blood_group"] = BloodGroup(model.blood_group)
    except ValueError:
        errors.append(f"blood_group: '{model.blood_group}' is not a valid blood group.")

    try:
        result["contact"] = validate_contact_number(model.contact or "")
    except ValueError as exc:
        errors.append(f"contact: {exc}")

    try:
        # Re-use EmailStr's validation via a throwaway model instead of importing
        # email-validator directly, keeping validation logic in one place.
        class _EmailCheck(BaseModel):
            email: EmailStr

        result["email"] = _EmailCheck(email=model.email or "").email
    except ValidationError:
        errors.append("email: not a valid email address.")

    try:
        result["address"] = AddressSchema(
            address_line=model.address_line or "",
            postcode=model.postcode or "",
            city_town=model.city_town or "",
        )
    except ValidationError as exc:
        for err in exc.errors():
            errors.append(f"address.{err['loc'][0]}: {err['msg']}")

    if errors:
        raise ValueError(
            "Patient details are required and must be valid when submitting a request for someone else: "
            + "; ".join(errors)
        )
    return result


class DonorResponseAction(BaseModel):
    request_id: str


class RejectRequestBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory reason for rejecting this request.")

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 5:
            raise ValueError("Please provide a reason of at least 5 characters.")
        return cleaned


class DonorIdBody(BaseModel):
    donor_id: str = Field(..., description="The _id of the donor_responses entry's donor (donor's user id).")


class BloodRequestResponse(BaseModel):
    id: str
    recipient_id: str
    for_self: bool
    patient: dict
    status: RequestStatus
    willing_donor_count: int
    hospital_approval_document_url: str
    created_at: str


class BloodRequestSummary(BaseModel):
    """
    Donor-facing summary shown in the matching-requests list. Deliberately
    includes enough of the recipient's identity (name, age, email) for a
    donor to make an informed decision about which request to open --
    contact number and the hospital document itself are reserved for the
    detail view (BloodRequestDonorDetail) so they're only fetched, and
    logged as accessed, when a donor actually opens a specific request.
    """
    id: str
    first_name: str
    last_name: str
    age: int
    blood_group: BloodGroup
    email: str
    city_town: str
    status: RequestStatus
    created_at: str
    distance_km: Optional[float] = None


class BloodRequestDonorDetail(BaseModel):
    """Full detail shown to an eligible donor after opening a specific request."""
    id: str
    for_self: bool
    first_name: str
    last_name: str
    age: int
    blood_group: BloodGroup
    contact: str
    email: str
    address: AddressSchema
    status: RequestStatus
    hospital_approval_document_url: str
    created_at: str
    distance_km: Optional[float] = None
    my_response_status: Optional[str] = None  # this donor's own prior response, if any


class OutreachStatusResponse(BaseModel):
    """Progress of the community-outreach pipeline (OSM lookup + contact scrape) for one request."""
    request_id: str
    status: str
    osm_job_status: Optional[str] = None
    contact_count: Optional[int] = None
    contacts_download_url: Optional[str] = None
    error: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None


class WillingDonorSummary(BaseModel):
    """A donor who volunteered for one of the recipient's requests, shown for accept/deny review."""
    donor_id: str
    first_name: str
    last_name: str
    age: int
    blood_group: BloodGroup
    contact: str
    email: str
    status: str
    responded_at: str
