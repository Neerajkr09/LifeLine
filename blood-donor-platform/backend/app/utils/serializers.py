"""Converts raw Mongo documents (with ObjectId / datetime) into JSON-safe dicts."""
from typing import Any


def serialize_user(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "role": doc["role"],
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "age": doc["age"],
        "blood_group": doc["blood_group"],
        "contact": doc["contact"],
        "email": doc["email"],
        "address": doc["address"],
        "location_sharing_permission": doc["location_sharing_permission"],
        "is_email_verified": doc["is_email_verified"],
        "is_active": doc["is_active"],
        "created_at": doc["created_at"].isoformat(),
    }


def serialize_blood_request(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "recipient_id": doc["recipient_id"],
        "for_self": doc["for_self"],
        "patient": doc["patient"],
        "status": doc["status"],
        "willing_donor_count": doc.get("willing_donor_count", 0),
        "hospital_approval_document_url": f"/api/v1/blood-requests/{doc['_id']}/document",
        "created_at": doc["created_at"].isoformat(),
    }


def serialize_blood_request_summary(doc: dict[str, Any], distance_km: float | None = None) -> dict[str, Any]:
    """
    Donor-facing list item. Deliberately includes name/age/email (enough to
    judge relevance) but not contact number or the document itself -- those
    are reserved for the detail view, see serialize_blood_request_donor_detail.
    """
    patient = doc["patient"]
    return {
        "id": str(doc["_id"]),
        "first_name": patient["first_name"],
        "last_name": patient["last_name"],
        "age": patient["age"],
        "blood_group": patient["blood_group"],
        "email": patient["email"],
        "city_town": patient["address"]["city_town"],
        "status": doc["status"],
        "created_at": doc["created_at"].isoformat(),
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
    }


def serialize_blood_request_donor_detail(
    doc: dict[str, Any], distance_km: float | None = None, my_response_status: str | None = None
) -> dict[str, Any]:
    """Full detail shown to an eligible donor once they open a specific request."""
    patient = doc["patient"]
    return {
        "id": str(doc["_id"]),
        "for_self": doc["for_self"],
        "first_name": patient["first_name"],
        "last_name": patient["last_name"],
        "age": patient["age"],
        "blood_group": patient["blood_group"],
        "contact": patient["contact"],
        "email": patient["email"],
        "address": patient["address"],
        "status": doc["status"],
        "hospital_approval_document_url": f"/api/v1/blood-requests/{doc['_id']}/document",
        "created_at": doc["created_at"].isoformat(),
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
        "my_response_status": my_response_status,
    }


def serialize_outreach_status(request_id: str, outreach: dict[str, Any]) -> dict[str, Any]:
    """
    Community-outreach progress for one blood request: nearby institutions
    found via OSM, and (once ready) a contact email compiled for each.
    """

    def _iso(value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else value

    return {
        "request_id": request_id,
        "status": outreach.get("status"),
        "osm_job_status": outreach.get("osm_job_status"),
        "contact_count": outreach.get("contact_count"),
        "contacts_download_url": (
            f"/api/v1/blood-requests/{request_id}/outreach/contacts"
            if outreach.get("status") == "ready"
            else None
        ),
        "error": outreach.get("error"),
        "submitted_at": _iso(outreach.get("submitted_at")),
        "completed_at": _iso(outreach.get("completed_at")),
    }


def serialize_willing_donor(response_doc: dict[str, Any], donor_doc: dict[str, Any]) -> dict[str, Any]:
    """A donor's response joined with that donor's own profile, for the recipient's review list."""
    return {
        "donor_id": str(donor_doc["_id"]),
        "first_name": donor_doc["first_name"],
        "last_name": donor_doc["last_name"],
        "age": donor_doc["age"],
        "blood_group": donor_doc["blood_group"],
        "contact": donor_doc["contact"],
        "email": donor_doc["email"],
        "status": response_doc["status"],
        "responded_at": response_doc["created_at"].isoformat(),
    }
