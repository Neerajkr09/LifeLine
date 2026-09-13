"""
MongoDB Atlas connection manager built on Motor (the async MongoDB driver).

A single AsyncIOMotorClient is created at application startup and reused for
the lifetime of the process (this is the recommended pattern -- Motor pools
connections internally, so there is no benefit to creating a new client per
request).
"""
import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, TEXT
from pymongo.errors import PyMongoError

from app.core.config import settings

logger = logging.getLogger("app.database")


class MongoDB:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongodb = MongoDB()


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency-friendly accessor for the current database handle."""
    if mongodb.db is None:
        raise RuntimeError("Database has not been initialized yet. Did startup run?")
    return mongodb.db


async def connect_to_mongo() -> None:
    logger.info("Connecting to MongoDB at %s ...", settings.MONGO_URI.split("@")[-1])
    mongodb.client = AsyncIOMotorClient(settings.MONGO_URI, uuidRepresentation="standard")
    mongodb.db = mongodb.client[settings.MONGO_DB_NAME]
    try:
        await mongodb.client.admin.command("ping")
        logger.info("MongoDB connection established.")
    except PyMongoError as exc:
        logger.error("Could not reach MongoDB: %s", exc)
        raise
    await ensure_indexes(mongodb.db)


async def close_mongo_connection() -> None:
    if mongodb.client is not None:
        mongodb.client.close()
        logger.info("MongoDB connection closed.")


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Create all indexes required by the platform. This is idempotent -- Mongo
    will no-op if an identical index already exists, so it is safe to run on
    every application startup instead of via a separate migration step.
    """
    # users: one document per donor/recipient, discriminated by `role`
    await db.users.create_index([("email", ASCENDING)], unique=True, name="uniq_email")
    await db.users.create_index([("role", ASCENDING)], name="idx_role")
    await db.users.create_index([("blood_group", ASCENDING)], name="idx_blood_group")
    await db.users.create_index([("location", GEOSPHERE)], name="idx_location_geo", sparse=True)
    await db.users.create_index([("is_deleted", ASCENDING)], name="idx_is_deleted")

    # blood_requests
    await db.blood_requests.create_index([("recipient_id", ASCENDING)], name="idx_recipient_id")
    await db.blood_requests.create_index([("blood_group", ASCENDING)], name="idx_request_blood_group")
    await db.blood_requests.create_index([("status", ASCENDING)], name="idx_request_status")
    await db.blood_requests.create_index([("location", GEOSPHERE)], name="idx_request_location_geo", sparse=True)
    await db.blood_requests.create_index([("created_at", DESCENDING)], name="idx_request_created_at")
    await db.blood_requests.create_index([("is_deleted", ASCENDING)], name="idx_request_is_deleted")

    # otps -- TTL index automatically purges expired / used OTP documents
    await db.otps.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expires_at")
    await db.otps.create_index([("email", ASCENDING), ("purpose", ASCENDING)], name="idx_email_purpose")

    # donor_responses -- a donor volunteering for a specific request
    await db.donor_responses.create_index(
        [("request_id", ASCENDING), ("donor_id", ASCENDING)], unique=True, name="uniq_request_donor"
    )
    await db.donor_responses.create_index([("donor_id", ASCENDING)], name="idx_response_donor_id")
    await db.donor_responses.create_index([("request_id", ASCENDING)], name="idx_response_request_id")
    await db.donor_responses.create_index(
        [("request_id", ASCENDING), ("status", ASCENDING)], name="idx_response_request_status"
    )

    logger.info("MongoDB indexes verified.")
