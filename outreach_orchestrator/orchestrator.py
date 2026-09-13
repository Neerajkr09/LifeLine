# """
# outreach_orchestrator: the completion watcher.

# Bridges the two halves of the outreach pipeline that don't talk to each
# other directly:

#   1. OsmProject's own worker (`python -m osmharvest run --follow`) fills in
#      search_job rows in osmharvest.db as it works through the Overpass
#      queue. This script does NOT do that job itself -- run the osmharvest
#      worker as its own long-lived process (see OsmProject/osmharvest.service).

#   2. email_outreach.pipeline scrapes a contact email for each place that has
#      a website but no OSM email tag.

# Every poll cycle, this script:
#   - looks in MongoDB for blood requests whose outreach is still
#     "osm_submitted" (set by the backend the moment a recipient's request
#     was created -- see app.services.outreach_service)
#   - checks each one's job status in osmharvest.db
#   - once a job is COMPLETED / COMPLETED_WITH_ERRORS, claims it (flips status
#     to "scraping" so a second orchestrator instance can't also pick it up),
#     runs the website-scraping stage, and writes the result back to Mongo

# Designed to run forever as its own systemd service, exactly like the
# osmharvest worker it depends on -- see outreach-worker.service.
# """

# from __future__ import annotations

# import argparse
# import csv
# import datetime as dt
# import logging
# import os
# import signal
# import time
# from pathlib import Path
# from typing import Optional

# try:
#     # Optional convenience: load a .env file next to this script (if present
#     # and python-dotenv is installed) before reading defaults from the
#     # environment below. Lets MONGO_URI/MONGO_DB survive across terminal
#     # restarts instead of needing `set`/`$env:` every session. Nothing here
#     # breaks if python-dotenv isn't installed -- CLI flags and manually-set
#     # environment variables still work exactly as before.
#     from dotenv import load_dotenv

#     load_dotenv(Path(__file__).resolve().parent / ".env")
# except ImportError:
#     pass

# from pymongo import MongoClient

# from osmharvest.exporters import export_job
# from osmharvest.store import JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS, Store

# from email_outreach.pipeline import process_places_csv

# LOGGER = logging.getLogger("outreach_orchestrator")

# TERMINAL_JOB_STATUSES = {JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS}


# class GracefulShutdown:
#     """Finish the sweep in progress on SIGINT/SIGTERM, then stop."""

#     def __init__(self) -> None:
#         self.requested = False
#         for sig in (signal.SIGINT, signal.SIGTERM):
#             try:
#                 signal.signal(sig, self._handle)
#             except (ValueError, OSError, AttributeError):
#                 pass  # not the main thread, or the platform lacks the signal

#     def _handle(self, *_args: object) -> None:
#         LOGGER.warning("Shutdown requested - finishing current sweep first")
#         self.requested = True


# def _mask_credentials(mongo_uri: str) -> str:
#     """mongodb+srv://user:secret@host/... -> mongodb+srv://user:***@host/... for safe logging."""
#     if "@" not in mongo_uri or "://" not in mongo_uri:
#         return mongo_uri
#     scheme, rest = mongo_uri.split("://", 1)
#     creds, _, host_and_path = rest.partition("@")
#     if ":" not in creds:
#         return mongo_uri
#     user, _, _password = creds.partition(":")
#     return f"{scheme}://{user}:***@{host_and_path}"


# def _count_contacts(contacts_csv: Path) -> int:
#     with contacts_csv.open("r", encoding="utf-8") as handle:
#         return max(sum(1 for _ in csv.reader(handle)) - 1, 0)  # minus header row


# def process_once(
#     mongo,
#     osm_db: Store,
#     export_dir: Path,
#     contacts_dir: Path,
#     max_places: Optional[int],
# ) -> int:
#     """One sweep over pending requests. Returns how many were advanced (to ready or failed)."""
#     advanced = 0
#     pending = list(mongo.blood_requests.find({"outreach.status": "osm_submitted"}))

#     for doc in pending:
#         request_id = str(doc["_id"])
#         outreach = doc.get("outreach") or {}
#         osm_request_id = outreach.get("osm_request_id")
#         if not osm_request_id:
#             continue

#         job = osm_db.get_job(osm_request_id)
#         if job is None:
#             LOGGER.warning("Request %s: osm job %s not found, marking failed", request_id, osm_request_id)
#             mongo.blood_requests.update_one(
#                 {"_id": doc["_id"], "outreach.status": "osm_submitted"},
#                 {"$set": {"outreach.status": "failed", "outreach.error": "osmharvest job disappeared"}},
#             )
#             advanced += 1
#             continue

#         if job["status"] not in TERMINAL_JOB_STATUSES:
#             continue  # still running -- check again next poll

#         # Claim it: the filter re-checks outreach.status so that if two
#         # orchestrator instances race on the same sweep, only one flips it.
#         claim = mongo.blood_requests.update_one(
#             {"_id": doc["_id"], "outreach.status": "osm_submitted"},
#             {"$set": {"outreach.status": "scraping"}},
#         )
#         if claim.modified_count == 0:
#             continue  # another orchestrator instance claimed it first

#         LOGGER.info(
#             "Request %s: osm job %s is %s, starting contact scrape",
#             request_id, osm_request_id, job["status"],
#         )

#         try:
#             export_job(osm_db, osm_request_id, export_dir)
#             places_csv = export_dir / osm_request_id / f"places_{osm_request_id}.csv"
#             contacts_csv = process_places_csv(
#                 request_id=osm_request_id,
#                 places_csv_path=places_csv,
#                 output_dir=contacts_dir,
#                 max_places=max_places,
#             )
#             contact_count = _count_contacts(contacts_csv)

#             mongo.blood_requests.update_one(
#                 {"_id": doc["_id"]},
#                 {
#                     "$set": {
#                         "outreach.status": "ready",
#                         "outreach.contacts_csv_path": str(contacts_csv),
#                         "outreach.contact_count": contact_count,
#                         "outreach.completed_at": dt.datetime.now(dt.timezone.utc),
#                         "outreach.error": None,
#                     }
#                 },
#             )
#             LOGGER.info("Request %s: outreach ready, %d contact(s)", request_id, contact_count)

#         except Exception as exc:  # noqa: BLE001 - one bad request must not kill the loop
#             LOGGER.exception("Request %s: outreach failed", request_id)
#             mongo.blood_requests.update_one(
#                 {"_id": doc["_id"]},
#                 {"$set": {"outreach.status": "failed", "outreach.error": str(exc)}},
#             )

#         advanced += 1

#     return advanced


# def main() -> int:
#     parser = argparse.ArgumentParser(
#         description="Watches for completed OSM harvest jobs and scrapes contact emails for them."
#     )
#     parser.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
#     parser.add_argument("--mongo-db", default=os.environ.get("MONGO_DB", "blood_donor_platform"))
#     parser.add_argument("--osm-db", default=os.environ.get("OSM_DB", "../OsmProject/osmharvest.db"))
#     parser.add_argument("--export-dir", default=os.environ.get("OSM_EXPORT_DIR", "../OsmProject/exports"))
#     parser.add_argument("--contacts-dir", default=os.environ.get("CONTACTS_DIR", "./contacts"))
#     parser.add_argument(
#         "--max-places",
#         type=int,
#         default=int(os.environ.get("MAX_PLACES", "40")),
#         help="Cap on nearest places scraped per request (0 = unlimited)",
#     )
#     parser.add_argument("--poll", type=float, default=float(os.environ.get("POLL_SECONDS", "30")), help="Seconds between sweeps")
#     parser.add_argument("--once", action="store_true", help="Run a single sweep and exit (useful for cron/testing)")
#     parser.add_argument("-v", "--verbose", action="store_true")
#     args = parser.parse_args()

#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s %(levelname)-7s %(message)s",
#         datefmt="%H:%M:%S",
#     )
#     # -v only makes *this script's* messages more detailed. Without this,
#     # `-v` sets the root logger to DEBUG, which pymongo inherits -- flooding
#     # the terminal with a heartbeat/command-tracing line roughly every
#     # second per Atlas replica member and burying the actual sweep output.
#     LOGGER.setLevel(logging.DEBUG if args.verbose else logging.INFO)
#     logging.getLogger("pymongo").setLevel(logging.WARNING)

#     max_places = None if not args.max_places else args.max_places

#     LOGGER.info(
#         "Starting: mongo=%s db=%s osm-db=%s poll=%ss max-places=%s",
#         _mask_credentials(args.mongo_uri), args.mongo_db, args.osm_db, args.poll, max_places or "unlimited",
#     )

#     client = MongoClient(args.mongo_uri)
#     mongo = client[args.mongo_db]
#     export_dir = Path(args.export_dir)
#     contacts_dir = Path(args.contacts_dir)

#     shutdown = GracefulShutdown()

#     try:
#         with Store(args.osm_db) as osm_db:
#             while not shutdown.requested:
#                 try:
#                     advanced = process_once(mongo, osm_db, export_dir, contacts_dir, max_places)
#                     LOGGER.info("Sweep complete: %d request(s) advanced", advanced)
#                 except Exception:  # noqa: BLE001 - a bad sweep must not kill the service
#                     LOGGER.exception("Sweep failed")

#                 if args.once:
#                     break

#                 deadline = time.monotonic() + args.poll
#                 while time.monotonic() < deadline and not shutdown.requested:
#                     time.sleep(min(1.0, deadline - time.monotonic()))
#     finally:
#         client.close()

#     return 0


# if __name__ == "__main__":
#     raise SystemExit(main())
"""
outreach_orchestrator: the completion watcher.

Bridges the two halves of the outreach pipeline that don't talk to each
other directly:

  1. OsmProject's own worker (`python -m osmharvest run --follow`) fills in
     search_job rows in osmharvest.db as it works through the Overpass
     queue. This script does NOT do that job itself -- run the osmharvest
     worker as its own long-lived process (see OsmProject/osmharvest.service).

  2. email_outreach.pipeline scrapes a contact email for each place that has
     a website but no OSM email tag.

Every poll cycle, this script:
  - looks in MongoDB for blood requests whose outreach is still
    "osm_submitted" (set by the backend the moment a recipient's request
    was created -- see app.services.outreach_service)
  - checks each one's job status in osmharvest.db
  - once a job is COMPLETED / COMPLETED_WITH_ERRORS, claims it (flips status
    to "scraping" so a second orchestrator instance can't also pick it up),
    runs the website-scraping stage, and writes the result back to Mongo

Designed to run forever as its own systemd service, exactly like the
osmharvest worker it depends on -- see outreach-worker.service.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
import signal
import time
from pathlib import Path
from typing import Optional

try:
    # Optional convenience: load a .env file next to this script (if present
    # and python-dotenv is installed) before reading defaults from the
    # environment below. Lets MONGO_URI/MONGO_DB survive across terminal
    # restarts instead of needing `set`/`$env:` every session. Nothing here
    # breaks if python-dotenv isn't installed -- CLI flags still work as
    # before.
    #
    # override=True is deliberate: without it, a stray already-set
    # environment variable (e.g. from a `setx` run during earlier testing,
    # which -- unlike `set` -- persists across every future terminal until
    # explicitly removed) would silently win over .env forever, with no
    # error and no way to tell from the .env file's contents alone. This
    # project's .env is meant to be the single source of truth for this
    # script, so it should always take precedence over ambient session state.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from pymongo import MongoClient

from osmharvest.exporters import export_job
from osmharvest.store import JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS, Store

from email_outreach.pipeline import process_places_csv

LOGGER = logging.getLogger("outreach_orchestrator")

TERMINAL_JOB_STATUSES = {JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS}


class GracefulShutdown:
    """Finish the sweep in progress on SIGINT/SIGTERM, then stop."""

    def __init__(self) -> None:
        self.requested = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle)
            except (ValueError, OSError, AttributeError):
                pass  # not the main thread, or the platform lacks the signal

    def _handle(self, *_args: object) -> None:
        LOGGER.warning("Shutdown requested - finishing current sweep first")
        self.requested = True


def _mask_credentials(mongo_uri: str) -> str:
    """mongodb+srv://user:secret@host/... -> mongodb+srv://user:***@host/... for safe logging."""
    if "@" not in mongo_uri or "://" not in mongo_uri:
        return mongo_uri
    scheme, rest = mongo_uri.split("://", 1)
    creds, _, host_and_path = rest.partition("@")
    if ":" not in creds:
        return mongo_uri
    user, _, _password = creds.partition(":")
    return f"{scheme}://{user}:***@{host_and_path}"


def _count_contacts(contacts_csv: Path) -> int:
    with contacts_csv.open("r", encoding="utf-8") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)  # minus header row


def process_once(
    mongo,
    osm_db: Store,
    export_dir: Path,
    contacts_dir: Path,
    max_places: Optional[int],
) -> int:
    """One sweep over pending requests. Returns how many were advanced (to ready or failed)."""
    advanced = 0
    pending = list(mongo.blood_requests.find({"outreach.status": "osm_submitted"}))

    for doc in pending:
        request_id = str(doc["_id"])
        outreach = doc.get("outreach") or {}
        osm_request_id = outreach.get("osm_request_id")
        if not osm_request_id:
            continue

        job = osm_db.get_job(osm_request_id)
        if job is None:
            LOGGER.warning("Request %s: osm job %s not found, marking failed", request_id, osm_request_id)
            mongo.blood_requests.update_one(
                {"_id": doc["_id"], "outreach.status": "osm_submitted"},
                {"$set": {"outreach.status": "failed", "outreach.error": "osmharvest job disappeared"}},
            )
            advanced += 1
            continue

        if job["status"] not in TERMINAL_JOB_STATUSES:
            continue  # still running -- check again next poll

        # Claim it: the filter re-checks outreach.status so that if two
        # orchestrator instances race on the same sweep, only one flips it.
        claim = mongo.blood_requests.update_one(
            {"_id": doc["_id"], "outreach.status": "osm_submitted"},
            {"$set": {"outreach.status": "scraping"}},
        )
        if claim.modified_count == 0:
            continue  # another orchestrator instance claimed it first

        LOGGER.info(
            "Request %s: osm job %s is %s, starting contact scrape",
            request_id, osm_request_id, job["status"],
        )

        try:
            export_job(osm_db, osm_request_id, export_dir)
            places_csv = export_dir / osm_request_id / f"places_{osm_request_id}.csv"
            contacts_csv = process_places_csv(
                request_id=osm_request_id,
                places_csv_path=places_csv,
                output_dir=contacts_dir,
                max_places=max_places,
            )
            contact_count = _count_contacts(contacts_csv)

            mongo.blood_requests.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "outreach.status": "ready",
                        "outreach.contacts_csv_path": str(contacts_csv),
                        "outreach.contact_count": contact_count,
                        "outreach.completed_at": dt.datetime.now(dt.timezone.utc),
                        "outreach.error": None,
                    }
                },
            )
            LOGGER.info("Request %s: outreach ready, %d contact(s)", request_id, contact_count)

        except Exception as exc:  # noqa: BLE001 - one bad request must not kill the loop
            LOGGER.exception("Request %s: outreach failed", request_id)
            mongo.blood_requests.update_one(
                {"_id": doc["_id"]},
                {"$set": {"outreach.status": "failed", "outreach.error": str(exc)}},
            )

        advanced += 1

    return advanced


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watches for completed OSM harvest jobs and scrapes contact emails for them."
    )
    parser.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--mongo-db", default=os.environ.get("MONGO_DB", "blood_donor_platform"))
    parser.add_argument("--osm-db", default=os.environ.get("OSM_DB", "../OsmProject/osmharvest.db"))
    parser.add_argument("--export-dir", default=os.environ.get("OSM_EXPORT_DIR", "../OsmProject/exports"))
    parser.add_argument("--contacts-dir", default=os.environ.get("CONTACTS_DIR", "./contacts"))
    parser.add_argument(
        "--max-places",
        type=int,
        default=int(os.environ.get("MAX_PLACES", "40")),
        help="Cap on nearest places scraped per request (0 = unlimited)",
    )
    parser.add_argument("--poll", type=float, default=float(os.environ.get("POLL_SECONDS", "30")), help="Seconds between sweeps")
    parser.add_argument("--once", action="store_true", help="Run a single sweep and exit (useful for cron/testing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # -v only makes *this script's* messages more detailed. Without this,
    # `-v` sets the root logger to DEBUG, which pymongo inherits -- flooding
    # the terminal with a heartbeat/command-tracing line roughly every
    # second per Atlas replica member and burying the actual sweep output.
    LOGGER.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    max_places = None if not args.max_places else args.max_places

    LOGGER.info(
        "Starting: mongo=%s db=%s osm-db=%s poll=%ss max-places=%s",
        _mask_credentials(args.mongo_uri), args.mongo_db, args.osm_db, args.poll, max_places or "unlimited",
    )

    client = MongoClient(args.mongo_uri)
    mongo = client[args.mongo_db]
    export_dir = Path(args.export_dir)
    contacts_dir = Path(args.contacts_dir)

    shutdown = GracefulShutdown()

    try:
        with Store(args.osm_db) as osm_db:
            while not shutdown.requested:
                try:
                    advanced = process_once(mongo, osm_db, export_dir, contacts_dir, max_places)
                    LOGGER.info("Sweep complete: %d request(s) advanced", advanced)
                except Exception:  # noqa: BLE001 - a bad sweep must not kill the service
                    LOGGER.exception("Sweep failed")

                if args.once:
                    break

                deadline = time.monotonic() + args.poll
                while time.monotonic() < deadline and not shutdown.requested:
                    time.sleep(min(1.0, deadline - time.monotonic()))
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())