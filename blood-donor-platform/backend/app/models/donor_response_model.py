"""
Donor response document model.

Represents a donor's decision on a specific blood request. This is what
powers the recipient dashboard's "Willing Donor Count" stat, the recipient's
"willing donors" review list, and the request-level rejection count used to
detect suspected-fraudulent requests.

Kept as its own collection (rather than an embedded array on the request)
because it is written independently by many different donors and benefits
from its own indexes and a uniqueness constraint (one response per donor per
request -- see core/database.py).

Status lifecycle for one donor's response to one request:

    WILLING ----(recipient accepts this donor)----> CONFIRMED
       |
       +--------(recipient denies this donor)-----> RECIPIENT_DECLINED
       |
       (donor never went WILLING; instead:)
DONOR_DECLINED   <- donor rejected the request outright, with a mandatory reason

A donor can only ever create ONE response per request (the unique index
enforces this) -- there is no "change your mind" path once you've either
volunteered or rejected, which keeps the reject-count-based ban check in
blood_request_controller.py meaningful (a donor can't reject, get counted,
then re-reject to inflate the count, nor can they reject after already
being confirmed).
"""
import datetime as dt
import enum
from typing import Any, Optional


class DonorResponseStatus(str, enum.Enum):
    WILLING = "willing"                        # donor volunteered; awaiting recipient decision
    CONFIRMED = "confirmed"                     # recipient accepted this donor; request closed
    RECIPIENT_DECLINED = "recipient_declined"    # recipient dismissed this donor (request stays open)
    DONOR_DECLINED = "donor_declined"            # donor rejected the request itself, with a reason


def build_donor_response_document(*, request_id: str, donor_id: str) -> dict[str, Any]:
    """A donor volunteering ('I'm willing to donate')."""
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "request_id": request_id,
        "donor_id": donor_id,
        "status": DonorResponseStatus.WILLING.value,
        "reject_reason": None,
        "created_at": now,
        "updated_at": now,
    }


def build_donor_rejection_document(*, request_id: str, donor_id: str, reason: str) -> dict[str, Any]:
    """A donor rejecting a request outright, with a mandatory reason."""
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "request_id": request_id,
        "donor_id": donor_id,
        "status": DonorResponseStatus.DONOR_DECLINED.value,
        "reject_reason": reason,
        "created_at": now,
        "updated_at": now,
    }
