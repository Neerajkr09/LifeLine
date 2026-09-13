from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.blood_request_model import RequestStatus
from app.models.donor_response_model import DonorResponseStatus
from app.utils.blood_compatibility import recipient_blood_groups_helpable_by_donor


async def get_recipient_dashboard_stats(db: AsyncIOMotorDatabase, recipient_id: str) -> dict:
    base_filter = {"recipient_id": recipient_id, "is_deleted": False}

    requests_raised = await db.blood_requests.count_documents(base_filter)
    successful_requests = await db.blood_requests.count_documents(
        {**base_filter, "status": RequestStatus.FULFILLED.value}
    )
    active_requests = await db.blood_requests.count_documents(
        {**base_filter, "status": RequestStatus.ACTIVE.value}
    )

    pipeline = [
        {"$match": base_filter},
        {"$group": {"_id": None, "total": {"$sum": "$willing_donor_count"}}},
    ]
    agg_result = await db.blood_requests.aggregate(pipeline).to_list(length=1)
    willing_donor_count = agg_result[0]["total"] if agg_result else 0

    return {
        "requests_raised": requests_raised,
        "successful_requests": successful_requests,
        "active_requests": active_requests,
        "willing_donor_count": willing_donor_count,
    }


async def get_donor_dashboard_stats(db: AsyncIOMotorDatabase, donor: dict) -> dict:
    helpable_groups = recipient_blood_groups_helpable_by_donor(donor["blood_group"])
    matching_requests_nearby = await db.blood_requests.count_documents(
        {
            "status": RequestStatus.ACTIVE.value,
            "is_deleted": False,
            "patient.blood_group": {"$in": helpable_groups},
        }
    )
    donor_id = str(donor["_id"])
    times_volunteered = await db.donor_responses.count_documents(
        {"donor_id": donor_id, "status": {"$ne": DonorResponseStatus.DONOR_DECLINED.value}}
    )
    confirmed_donations = await db.donor_responses.count_documents(
        {"donor_id": donor_id, "status": DonorResponseStatus.CONFIRMED.value}
    )

    return {
        "matching_requests_nearby": matching_requests_nearby,
        "times_volunteered": times_volunteered,
        "confirmed_donations": confirmed_donations,
    }
