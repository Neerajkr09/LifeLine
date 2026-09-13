from motor.motor_asyncio import AsyncIOMotorDatabase

from app.utils.serializers import serialize_user


async def get_profile(current_user: dict) -> dict:
    return serialize_user(current_user)


async def count_active_donors_for_blood_group(db: AsyncIOMotorDatabase, blood_group: str) -> int:
    return await db.users.count_documents(
        {"role": "donor", "blood_group": blood_group, "is_deleted": False, "is_active": True}
    )
