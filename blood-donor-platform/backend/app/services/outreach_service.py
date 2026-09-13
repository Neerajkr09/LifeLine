"""
Hands a newly-created blood request's location off to osmharvest (a sibling
project, installed in this environment as the `osmharvest` package -- see
../../OsmProject and the integration README at the repo root).

Submitting a job is a fast, local sqlite insert with no network call, so it
is safe to run inline while creating a blood request. The actual Overpass
fetching and the website-scraping stage both happen out-of-process, in
long-lived worker processes:

    OsmProject:            `python -m osmharvest run --follow`
    outreach_orchestrator: `python orchestrator.py`

This module never blocks the recipient waiting on either of those. A
recipient's blood request is life-critical and must be created successfully
even if outreach's sqlite file is missing, locked, or misconfigured -- so
every function below catches broadly and returns a NOT_STARTED/FAILED state
dict instead of raising.
"""

import asyncio
import datetime as dt
import logging
from typing import Optional

from app.core.config import settings
from app.models.blood_request_model import OutreachStatus

logger = logging.getLogger("app.outreach")


def _submit_sync(latitude: float, longitude: float) -> str:
    """
    Runs on a worker thread via asyncio.to_thread -- osmharvest.Store is a
    synchronous sqlite wrapper, not an asyncio one.
    """
    from osmharvest.store import Store
    from osmharvest.worker import plan_job

    with Store(settings.OSM_DB_PATH) as db:
        request_id = db.generate_request_id()
        db.create_job(
            request_id=request_id,
            latitude=latitude,
            longitude=longitude,
            radius_metres=settings.OUTREACH_RADIUS_METRES,
            categories=settings.outreach_categories_list,
        )
        plan_job(db, request_id)
    return request_id


async def submit_outreach_job(latitude: Optional[float], longitude: Optional[float]) -> dict:
    """
    Best-effort. Returns a dict of fields to merge into a blood request's
    `outreach` sub-document. Never raises -- a failure here degrades to
    OutreachStatus.NOT_STARTED, it never prevents the blood request itself
    from being created.
    """
    if not settings.OUTREACH_ENABLED:
        return {"status": OutreachStatus.DISABLED.value}

    if latitude is None or longitude is None:
        return {"status": OutreachStatus.NOT_STARTED.value, "error": "No location on this request."}

    try:
        osm_request_id = await asyncio.to_thread(_submit_sync, latitude, longitude)
    except Exception as exc:  # noqa: BLE001 - outreach must never break request creation
        logger.exception("Failed to submit outreach job for (%s, %s)", latitude, longitude)
        return {"status": OutreachStatus.NOT_STARTED.value, "error": str(exc)}

    logger.info("Outreach job %s submitted for (%s, %s)", osm_request_id, latitude, longitude)
    return {
        "status": OutreachStatus.OSM_SUBMITTED.value,
        "osm_request_id": osm_request_id,
        "submitted_at": dt.datetime.now(dt.timezone.utc),
        "error": None,
    }


def _read_job_status_sync(osm_request_id: str) -> Optional[str]:
    from osmharvest.store import Store

    with Store(settings.OSM_DB_PATH) as db:
        job = db.get_job(osm_request_id)
        return job["status"] if job is not None else None


async def read_osm_job_status(osm_request_id: str) -> Optional[str]:
    """
    Best-effort live status straight from osmharvest's sqlite db (PENDING /
    RUNNING / COMPLETED / COMPLETED_WITH_ERRORS), so the outreach status
    endpoint can show progress even before outreach_orchestrator has moved a
    request into SCRAPING/READY. Returns None on any error.
    """
    try:
        return await asyncio.to_thread(_read_job_status_sync, osm_request_id)
    except Exception:  # noqa: BLE001 - purely informational, never fatal
        logger.exception("Failed to read osmharvest status for %s", osm_request_id)
        return None
