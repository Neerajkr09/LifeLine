"""
Blood request document model.

A blood request is created once by a recipient and is then immutable by
design (see business rule in the spec: "Submitted request cannot be
edited"). The only fields that change post-creation are system-managed
lifecycle fields: `status`, `willing_donor_count`, `updated_at` -- these are
mutated exclusively by the controller layer in response to donor actions,
never by a user-supplied "edit" endpoint.
"""
import datetime as dt
import enum
from typing import Any, Optional

from app.models.user_model import Address, GeoPoint


class RequestStatus(str, enum.Enum):
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class OutreachStatus(str, enum.Enum):
    """
    Lifecycle of the community-outreach side effect of a request: find nearby
    colleges/restaurants/pubs via OSM, then scrape a contact email for each.
    This never blocks or fails the blood request itself -- see
    app.services.outreach_service.
    """

    DISABLED = "disabled"           # OUTREACH_ENABLED=false
    NOT_STARTED = "not_started"     # submission itself failed; request still created fine
    OSM_SUBMITTED = "osm_submitted"  # queued with osmharvest, awaiting Overpass results
    SCRAPING = "scraping"           # osmharvest finished; outreach_orchestrator is scraping websites
    READY = "ready"                 # contacts CSV is available
    FAILED = "failed"               # something went wrong after submission; see error


def build_blood_request_document(
    *,
    recipient_id: str,
    for_self: bool,
    first_name: str,
    last_name: str,
    age: int,
    blood_group: str,
    contact: str,
    email: str,
    address: Address,
    location: Optional[GeoPoint],
    hospital_approval_document_path: str,
    hospital_approval_document_type: str,
) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "recipient_id": recipient_id,
        "for_self": for_self,
        "patient": {
            "first_name": first_name,
            "last_name": last_name,
            "age": age,
            "blood_group": blood_group,
            "contact": contact,
            "email": email.lower().strip(),
            "address": dict(address),
        },
        "location": dict(location) if location else None,
        "hospital_approval_document": {
            "path": hospital_approval_document_path,
            "content_type": hospital_approval_document_type,
        },
        "status": RequestStatus.ACTIVE.value,
        "willing_donor_count": 0,
        "outreach": {
            "status": OutreachStatus.NOT_STARTED.value,
            "osm_request_id": None,
            "contacts_csv_path": None,
            "contact_count": None,
            "error": None,
            "submitted_at": None,
            "completed_at": None,
        },
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
