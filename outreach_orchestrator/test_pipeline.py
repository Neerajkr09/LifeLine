"""
test_pipeline.py -- standalone testing tool.

Exercises osmharvest + email_outreach directly. Zero involvement from
MongoDB, the backend, or the blood-donor-platform frontend -- nothing here
touches a blood request or writes to `outreach.status` anywhere. Use this to
try a new location, or a CSV you already have, without submitting a fake
request through the app first.

Two independent modes:

  1. Test a location end-to-end (real OSM harvest, then real scrape):
     python test_pipeline.py --lat 18.5476 --lng 73.9355 --radius 5000

  2. Test scraping only, against a places CSV you already have -- skips OSM
     entirely, so this works with your own custom CSV too (only needs a
     `website` column; `email`, `name`, `category`, `distance_metres` are
     used if present, blank if not):
     python test_pipeline.py --places-csv my_700_rows.csv --max-places 30

Both modes print a live per-site log as they go (SUCCESS / NO_EMAIL /
HIGH_SECURITY / SCRAPE_ERROR / etc. -- see email_outreach's pipeline.py),
so you can see *why* a site did or didn't yield an email, not just the
final count. This is the same logging the real outreach_orchestrator uses,
so what you see here is what you'd see in production too.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from osmharvest.exporters import export_job
from osmharvest.overpass import OverpassClient
from osmharvest.store import Store
from osmharvest.worker import Worker, plan_job

from email_outreach.pipeline import process_places_csv

LOGGER = logging.getLogger("test_pipeline")


def run_location_test(args: argparse.Namespace) -> Path:
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    with Store(args.osm_db) as db:
        request_id = args.request_id or db.generate_request_id()
        LOGGER.info(
            "Submitting: %s, %s within %sm | %s -> request id %s",
            args.lat, args.lng, args.radius, ", ".join(categories), request_id,
        )
        db.create_job(
            request_id=request_id, latitude=args.lat, longitude=args.lng,
            radius_metres=args.radius, categories=categories,
        )
        plan_job(db, request_id)

        client = OverpassClient()
        worker = Worker(db, client, batch_size=200, export_dir=Path(args.export_dir))
        # follow=False + an explicit request_id: single-shot, drains only
        # this job's tasks, then returns -- no dependency on run_worker.bat
        # or any other process being up.
        worker.run(request_id=request_id, follow=False)

        job = db.get_job(request_id)
        LOGGER.info("OSM harvest finished: status=%s", job["status"])

    places_csv = Path(args.export_dir) / request_id / f"places_{request_id}.csv"
    if not places_csv.exists():
        raise SystemExit(f"Expected {places_csv} but it wasn't created -- check the OSM harvest log above for errors.")

    return _scrape(request_id, places_csv, args)


def run_csv_test(args: argparse.Namespace) -> Path:
    request_id = args.request_id or "CSVTEST"
    places_csv = Path(args.places_csv)
    if not places_csv.exists():
        raise SystemExit(f"--places-csv not found: {places_csv}")
    LOGGER.info("Skipping OSM entirely -- scraping directly from %s", places_csv)
    return _scrape(request_id, places_csv, args)


def _scrape(request_id: str, places_csv: Path, args: argparse.Namespace) -> Path:
    LOGGER.info("Starting contact scrape (max_places=%s)...", args.max_places or "unlimited")
    contacts_csv = process_places_csv(
        request_id=request_id,
        places_csv_path=places_csv,
        output_dir=args.contacts_dir,
        max_places=args.max_places,
    )

    import csv as csv_module
    with contacts_csv.open("r", encoding="utf-8") as handle:
        rows = list(csv_module.DictReader(handle))

    print()
    print("=" * 60)
    print(f"DONE: {len(rows)} contact(s) written to {contacts_csv}")
    if rows:
        from_osm = sum(1 for r in rows if r["source"] == "osm_tag")
        from_scrape = sum(1 for r in rows if r["source"] == "scraped_website")
        print(f"  {from_osm} from OSM tags (free, no scrape needed)")
        print(f"  {from_scrape} from scraping a website")
    print("=" * 60)
    return contacts_csv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--request-id", default=None, help="Reuse a specific id (default: auto-generated / 'CSVTEST')")
    parser.add_argument("--max-places", type=int, default=int(os.environ.get("MAX_PLACES", "40")))
    parser.add_argument("--contacts-dir", default=os.environ.get("CONTACTS_DIR", "./contacts"))
    parser.add_argument("-v", "--verbose", action="store_true")

    location = parser.add_argument_group("mode 1: test a location (drives a real OSM harvest)")
    location.add_argument("--lat", type=float)
    location.add_argument("--lng", type=float)
    location.add_argument("--radius", type=float, default=5000.0)
    location.add_argument("--categories", default="college,university,restaurant,pub")
    location.add_argument("--osm-db", default=os.environ.get("OSM_DB", "../OsmProject/osmharvest.db"))
    location.add_argument("--export-dir", default=os.environ.get("OSM_EXPORT_DIR", "../OsmProject/exports"))

    csv_mode = parser.add_argument_group("mode 2: test scraping only, against an existing CSV")
    csv_mode.add_argument("--places-csv", help="Skips OSM harvesting entirely if given")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if args.places_csv:
        run_csv_test(args)
    elif args.lat is not None and args.lng is not None:
        run_location_test(args)
    else:
        parser.error("Give either --places-csv (mode 2), or both --lat and --lng (mode 1).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())