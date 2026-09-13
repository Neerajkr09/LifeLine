from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError

from app.controllers import blood_request_controller
from app.core.database import get_database
from app.dependencies.auth_dependency import CurrentUser, require_role
from app.models.user_model import Role
from app.schemas.blood_request_schema import (
    BloodRequestCreate,
    BloodRequestDonorDetail,
    BloodRequestResponse,
    BloodRequestSummary,
    DonorIdBody,
    OutreachStatusResponse,
    RejectRequestBody,
    WillingDonorSummary,
)
from app.schemas.common_schema import GeoLocationSchema, MessageResponse

router = APIRouter(prefix="/blood-requests", tags=["Blood Requests"])


@router.post("", response_model=BloodRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_blood_request(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
    for_self: bool = Form(...),
    for_other: bool = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    age: int = Form(0),
    blood_group: str = Form(""),
    contact: str = Form(""),
    email: str = Form(""),
    address_line: str = Form(""),
    postcode: str = Form(""),
    city_town: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    accepted_warning: bool = Form(False),
    document: UploadFile = File(..., description="Hospital approval form (PDF or image)"),
):
    """
    Multipart/form-data endpoint (a file upload is mandatory alongside the
    request fields, so this cannot be a plain JSON body). All fields are
    re-validated server-side via BloodRequestCreate regardless of what the
    frontend already checked client-side.
    """
    try:
        payload = BloodRequestCreate(
            for_self=for_self,
            for_other=for_other,
            first_name=first_name,
            last_name=last_name,
            age=age,
            blood_group=blood_group,
            contact=contact,
            email=email,
            address_line=address_line,
            postcode=postcode,
            city_town=city_town,
            location=GeoLocationSchema(latitude=latitude, longitude=longitude),
            accepted_warning=accepted_warning,
        )
    except ValidationError as exc:
        sanitized_errors = [
            {"field": ".".join(str(p) for p in err["loc"]) or "request", "message": err["msg"]}
            for err in exc.errors()
        ]
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=sanitized_errors)

    return await blood_request_controller.create_blood_request(db, current_user, payload, document)


@router.get("/mine", response_model=list[BloodRequestResponse])
async def list_my_requests(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    return await blood_request_controller.list_my_requests(db, str(current_user["_id"]))


@router.get("/matching", response_model=list[BloodRequestSummary])
async def list_matching_requests(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.DONOR))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return await blood_request_controller.list_matching_requests_for_donor(db, current_user, page, page_size)


@router.get("/{request_id}/detail", response_model=BloodRequestDonorDetail)
async def get_matching_request_detail(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.DONOR))],
):
    """
    Full recipient detail (name, age, blood group, email, address, and a
    link to the hospital approval document) for one specific matching
    request, shown before a donor decides to volunteer or reject. Contact
    number is included here but deliberately withheld from the /matching
    list view.
    """
    return await blood_request_controller.get_matching_request_detail(db, current_user, request_id)


@router.post("/{request_id}/volunteer", response_model=MessageResponse)
async def volunteer_as_donor(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.DONOR))],
):
    return await blood_request_controller.volunteer_as_donor(db, current_user, request_id)


@router.post("/{request_id}/reject", response_model=MessageResponse)
async def reject_request(
    request_id: str,
    payload: RejectRequestBody,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.DONOR))],
):
    """
    Donor rejects a request outright with a mandatory reason. If a single
    request accumulates enough rejections (see settings.DONOR_REJECTION_BAN_THRESHOLD),
    the recipient's account is automatically banned and the request cancelled.
    """
    return await blood_request_controller.reject_request(db, current_user, request_id, payload.reason)


@router.get("/{request_id}/willing-donors", response_model=list[WillingDonorSummary])
async def list_willing_donors(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    """Recipient-only: everyone currently WILLING on one of their own requests, for accept/deny review."""
    return await blood_request_controller.list_willing_donors(db, str(current_user["_id"]), request_id)


@router.post("/{request_id}/accept-donor", response_model=MessageResponse)
async def accept_donor(
    request_id: str,
    payload: DonorIdBody,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    return await blood_request_controller.accept_donor(db, str(current_user["_id"]), request_id, payload.donor_id)


@router.post("/{request_id}/deny-donor", response_model=MessageResponse)
async def deny_donor(
    request_id: str,
    payload: DonorIdBody,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    return await blood_request_controller.deny_donor(db, str(current_user["_id"]), request_id, payload.donor_id)


@router.get("/{request_id}/document")
async def download_hospital_document(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: CurrentUser,
):
    """
    Available to the recipient who owns the request, and to any donor who is
    currently eligible for it (compatible blood group, request active, and
    within the matching radius) -- see _donor_eligibility_distance_km.
    """
    path = await blood_request_controller.get_request_document_path(db, request_id, current_user)
    return FileResponse(path)


@router.get("/{request_id}/outreach", response_model=OutreachStatusResponse)
async def get_outreach_status(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    """
    Recipient-only: progress of the community-outreach pipeline for this
    request -- nearby colleges/restaurants/pubs found via OSM, and (once
    ready) how many contact emails were compiled for them.
    """
    return await blood_request_controller.get_outreach_status(db, current_user, request_id)


@router.get("/{request_id}/outreach/contacts")
async def download_outreach_contacts(
    request_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    """Recipient-only: download the compiled contacts CSV, once outreach status is 'ready'."""
    path = await blood_request_controller.get_outreach_contacts_path(db, current_user, request_id)
    return FileResponse(path, filename=f"outreach_contacts_{request_id}.csv", media_type="text/csv")
