import datetime as dt
import logging

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.controllers.auth_controller import consume_verified_otp
from app.core.config import settings
from app.models.blood_request_model import OutreachStatus, RequestStatus, build_blood_request_document
from app.models.donor_response_model import (
    DonorResponseStatus,
    build_donor_rejection_document,
    build_donor_response_document,
)
from app.schemas.blood_request_schema import BloodRequestCreate
from app.services import outreach_service
from app.utils.blood_compatibility import can_donor_help_recipient, recipient_blood_groups_helpable_by_donor
from app.utils.file_utils import save_hospital_approval_document
from app.utils.geo import haversine_km
from app.utils.serializers import (
    serialize_blood_request,
    serialize_blood_request_donor_detail,
    serialize_blood_request_summary,
    serialize_outreach_status,
    serialize_willing_donor,
)

logger = logging.getLogger("app.blood_requests")

DONOR_MATCH_RADIUS_KM = 5.0


async def create_blood_request(
    db: AsyncIOMotorDatabase,
    current_user: dict,
    payload: BloodRequestCreate,
    document: UploadFile,
) -> dict:
    if payload.for_self:
        # Never trust client-supplied identity fields for a self-request --
        # always source them from the authenticated user's own profile.
        first_name = current_user["first_name"]
        last_name = current_user["last_name"]
        age = current_user["age"]
        blood_group = current_user["blood_group"]
        contact = current_user["contact"]
        email = current_user["email"]
        address = current_user["address"]
    else:
        # for_other: a verified OTP for this specific (possibly third-party) email is required.
        other = payload.other_patient_fields()
        await consume_verified_otp(db, other["email"], "blood_request")
        first_name = other["first_name"]
        last_name = other["last_name"]
        age = other["age"]
        blood_group = other["blood_group"].value
        contact = other["contact"]
        email = other["email"]
        address = other["address"].model_dump()

    stored_path, content_type = await save_hospital_approval_document(document)

    doc = build_blood_request_document(
        recipient_id=str(current_user["_id"]),
        for_self=payload.for_self,
        first_name=first_name,
        last_name=last_name,
        age=age,
        blood_group=blood_group,
        contact=contact,
        email=email,
        address=address,
        location=payload.location.to_geojson(),
        hospital_approval_document_path=stored_path,
        hospital_approval_document_type=content_type,
    )
    result = await db.blood_requests.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Community outreach: hand this request's location off to osmharvest so
    # nearby colleges/restaurants/pubs can be found and (eventually) a
    # contact email compiled for each -- see app.services.outreach_service
    # and outreach_orchestrator/ for the rest of the pipeline. This is a
    # best-effort side effect: it never raises, and a failure here does not
    # affect the blood request that was just created.
    location = doc.get("location")
    latitude = location["coordinates"][1] if location else None
    longitude = location["coordinates"][0] if location else None
    outreach_update = await outreach_service.submit_outreach_job(latitude, longitude)
    if outreach_update:
        doc["outreach"].update(outreach_update)
        await db.blood_requests.update_one(
            {"_id": result.inserted_id}, {"$set": {"outreach": doc["outreach"]}}
        )

    return serialize_blood_request(doc)


async def list_my_requests(db: AsyncIOMotorDatabase, recipient_id: str) -> list[dict]:
    cursor = db.blood_requests.find(
        {"recipient_id": recipient_id, "is_deleted": False}
    ).sort("created_at", -1)
    return [serialize_blood_request(doc) async for doc in cursor]


async def _find_request_or_404(db: AsyncIOMotorDatabase, request_id: str) -> tuple[ObjectId, dict]:
    try:
        oid = ObjectId(request_id)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found.")
    doc = await db.blood_requests.find_one({"_id": oid, "is_deleted": False})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found.")
    return oid, doc


def _donor_eligibility_distance_km(donor: dict, request_doc: dict) -> float | None:
    """
    Raises 403 if this donor isn't allowed to see this request's detail/
    document, otherwise returns the distance in km (or None if it can't be
    computed because one side hasn't shared a location). Eligibility is:
    blood-group compatible, request currently active, and -- when both
    donor and request have a location on file -- within DONOR_MATCH_RADIUS_KM.
    A donor missing location data isn't blocked outright, matching the same
    lenient fallback used by the matching feed itself.
    """
    if request_doc["status"] != RequestStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This request is no longer active.")
    if not can_donor_help_recipient(donor["blood_group"], request_doc["patient"]["blood_group"]):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This request isn't a blood-group match for your profile."
        )

    distance_km = haversine_km(donor.get("location"), request_doc.get("location"))
    if distance_km is not None and distance_km > DONOR_MATCH_RADIUS_KM:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This request is outside the {DONOR_MATCH_RADIUS_KM:.0f}km matching radius.",
        )
    return distance_km


async def get_request_document_path(db: AsyncIOMotorDatabase, request_id: str, current_user: dict) -> str:
    oid, doc = await _find_request_or_404(db, request_id)

    is_owner = doc["recipient_id"] == str(current_user["_id"])
    if not is_owner:
        if current_user["role"] != "donor":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this document.")
        # Raises 403 itself if this donor isn't eligible for this request.
        _donor_eligibility_distance_km(current_user, doc)

    return doc["hospital_approval_document"]["path"]


async def list_matching_requests_for_donor(
    db: AsyncIOMotorDatabase, donor: dict, page: int = 1, page_size: int = 20
) -> list[dict]:
    helpable_groups = recipient_blood_groups_helpable_by_donor(donor["blood_group"])
    base_match = {
        "status": RequestStatus.ACTIVE.value,
        "is_deleted": False,
        "patient.blood_group": {"$in": helpable_groups},
    }
    skip = max(page - 1, 0) * page_size

    donor_location = donor.get("location")
    if donor_location and donor.get("location_sharing_permission"):
        pipeline = [
            {
                "$geoNear": {
                    "near": donor_location,
                    "distanceField": "distance_meters",
                    "maxDistance": DONOR_MATCH_RADIUS_KM * 1000,  # $geoNear wants metres
                    "spherical": True,
                    "query": base_match,
                }
            },
            {"$skip": skip},
            {"$limit": page_size},
        ]
        try:
            results = []
            async for doc in db.blood_requests.aggregate(pipeline):
                distance_km = doc.get("distance_meters", 0) / 1000
                results.append(serialize_blood_request_summary(doc, distance_km=distance_km))
            return results
        except Exception as exc:  # noqa: BLE001 -- deliberately broad, see comment above
            logger.warning("Geo-sorted donor matching query failed, falling back to newest-first: %s", exc)

    # No donor location on file (or the geo query failed) -- fall back to
    # newest-first, no distance sort.
    cursor = (
        db.blood_requests.find(base_match)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    return [serialize_blood_request_summary(doc) async for doc in cursor]


async def get_matching_request_detail(db: AsyncIOMotorDatabase, donor: dict, request_id: str) -> dict:
    """Full detail view a donor sees after opening a specific matching request."""
    oid, request_doc = await _find_request_or_404(db, request_id)
    donor_id = str(donor["_id"])
    if request_doc["recipient_id"] == donor_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot view your own request as a donor.")

    distance_km = _donor_eligibility_distance_km(donor, request_doc)  # raises 403 if ineligible

    my_response = await db.donor_responses.find_one({"request_id": request_id, "donor_id": donor_id})
    my_response_status = my_response["status"] if my_response else None

    return serialize_blood_request_donor_detail(
        request_doc, distance_km=distance_km, my_response_status=my_response_status
    )


async def volunteer_as_donor(db: AsyncIOMotorDatabase, donor: dict, request_id: str) -> dict:
    donor_id = str(donor["_id"])
    oid, request_doc = await _find_request_or_404(db, request_id)
    if request_doc["recipient_id"] == donor_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot volunteer for your own request.")
    # Re-validates compatibility/active-status/radius server-side -- never trust
    # that the client only ever calls this for a request it legitimately showed.
    _donor_eligibility_distance_km(donor, request_doc)

    response_doc = build_donor_response_document(request_id=request_id, donor_id=donor_id)
    try:
        await db.donor_responses.insert_one(response_doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already responded to this request.")

    await db.blood_requests.update_one(
        {"_id": oid},
        {"$inc": {"willing_donor_count": 1}, "$set": {"updated_at": dt.datetime.now(dt.timezone.utc)}},
    )
    return {
        "success": True,
        "message": "Thank you for showing up for this good cause! The recipient can now see your details and will reach out if they choose you.",
    }


async def reject_request(db: AsyncIOMotorDatabase, donor: dict, request_id: str, reason: str) -> dict:
    donor_id = str(donor["_id"])
    oid, request_doc = await _find_request_or_404(db, request_id)
    if request_doc["recipient_id"] == donor_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot reject your own request.")
    _donor_eligibility_distance_km(donor, request_doc)  # same eligibility rules as volunteering

    rejection_doc = build_donor_rejection_document(request_id=request_id, donor_id=donor_id, reason=reason)
    try:
        await db.donor_responses.insert_one(rejection_doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already responded to this request.")

    rejection_count = await db.donor_responses.count_documents(
        {"request_id": request_id, "status": DonorResponseStatus.DONOR_DECLINED.value}
    )

    banned = False
    if rejection_count >= settings.DONOR_REJECTION_BAN_THRESHOLD:
        try:
            recipient_oid = ObjectId(request_doc["recipient_id"])
            await db.users.update_one(
                {"_id": recipient_oid},
                {"$set": {"is_banned": True, "updated_at": dt.datetime.now(dt.timezone.utc)}},
            )
            await db.blood_requests.update_one(
                {"_id": oid},
                {"$set": {"status": RequestStatus.CANCELLED.value, "updated_at": dt.datetime.now(dt.timezone.utc)}},
            )
            banned = True
            logger.warning(
                "Recipient %s auto-banned: request %s reached %d donor rejections (threshold=%d).",
                request_doc["recipient_id"], request_id, rejection_count, settings.DONOR_REJECTION_BAN_THRESHOLD,
            )
        except (InvalidId, TypeError):
            logger.error("Could not auto-ban recipient %s: invalid id.", request_doc["recipient_id"])

    message = (
        "Thanks for the feedback -- this request has now been flagged and closed for review."
        if banned
        else "Thanks for letting us know. This request has been marked as declined by you."
    )
    return {"success": True, "message": message}


async def list_willing_donors(db: AsyncIOMotorDatabase, recipient_id: str, request_id: str) -> list[dict]:
    """Recipient-only: donors who are currently WILLING on one of their own requests."""
    _oid, request_doc = await _find_request_or_404(db, request_id)
    if request_doc["recipient_id"] != recipient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this request's donors.")

    results = []
    cursor = db.donor_responses.find(
        {"request_id": request_id, "status": DonorResponseStatus.WILLING.value}
    ).sort("created_at", 1)
    async for resp in cursor:
        try:
            donor_oid = ObjectId(resp["donor_id"])
        except (InvalidId, TypeError):
            continue
        donor_doc = await db.users.find_one({"_id": donor_oid, "is_deleted": False})
        if donor_doc is not None:
            results.append(serialize_willing_donor(resp, donor_doc))
    return results


async def accept_donor(db: AsyncIOMotorDatabase, recipient_id: str, request_id: str, donor_id: str) -> dict:
    """Recipient accepts one specific willing donor: closes the request, everyone else's feed updates naturally."""
    oid, request_doc = await _find_request_or_404(db, request_id)
    if request_doc["recipient_id"] != recipient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this request.")
    if request_doc["status"] != RequestStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is no longer active.")

    result = await db.donor_responses.update_one(
        {"request_id": request_id, "donor_id": donor_id, "status": DonorResponseStatus.WILLING.value},
        {"$set": {"status": DonorResponseStatus.CONFIRMED.value, "updated_at": dt.datetime.now(dt.timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This donor is not currently a willing responder for this request.")

    # Closing the request here is what removes it from every donor's matching
    # feed -- that feed only ever queries status == active (see
    # list_matching_requests_for_donor), so no separate "remove" step is needed.
    await db.blood_requests.update_one(
        {"_id": oid},
        {"$set": {"status": RequestStatus.FULFILLED.value, "updated_at": dt.datetime.now(dt.timezone.utc)}},
    )
    return {
        "success": True,
        "message": "Please contact the donor and meet at the hospital/clinic whose approval document was uploaded!",
    }


async def deny_donor(db: AsyncIOMotorDatabase, recipient_id: str, request_id: str, donor_id: str) -> dict:
    """Recipient dismisses one specific willing donor; the request itself stays open to others."""
    _oid, request_doc = await _find_request_or_404(db, request_id)
    if request_doc["recipient_id"] != recipient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this request.")

    result = await db.donor_responses.update_one(
        {"request_id": request_id, "donor_id": donor_id, "status": DonorResponseStatus.WILLING.value},
        {"$set": {"status": DonorResponseStatus.RECIPIENT_DECLINED.value, "updated_at": dt.datetime.now(dt.timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This donor is not currently a willing responder for this request.")
    return {"success": True, "message": "Donor removed from your list."}


async def get_outreach_status(db: AsyncIOMotorDatabase, current_user: dict, request_id: str) -> dict:
    """
    Recipient-only: progress of the community-outreach pipeline for one of
    their own requests. Refreshes with a live read from osmharvest's sqlite
    db while still OSM_SUBMITTED, so progress is visible even before
    outreach_orchestrator has moved the request into SCRAPING/READY.
    """
    _oid, doc = await _find_request_or_404(db, request_id)
    if doc["recipient_id"] != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this request's outreach data.")

    outreach = dict(doc.get("outreach") or {})
    if outreach.get("status") == OutreachStatus.OSM_SUBMITTED.value and outreach.get("osm_request_id"):
        live_status = await outreach_service.read_osm_job_status(outreach["osm_request_id"])
        if live_status:
            outreach["osm_job_status"] = live_status

    return serialize_outreach_status(str(doc["_id"]), outreach)


async def get_outreach_contacts_path(db: AsyncIOMotorDatabase, current_user: dict, request_id: str) -> str:
    """Recipient-only: filesystem path of the compiled contacts CSV, once ready."""
    _oid, doc = await _find_request_or_404(db, request_id)
    if doc["recipient_id"] != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this request's outreach data.")

    outreach = doc.get("outreach") or {}
    if outreach.get("status") != OutreachStatus.READY.value or not outreach.get("contacts_csv_path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outreach contacts are not ready yet for this request.")

    return outreach["contacts_csv_path"]
