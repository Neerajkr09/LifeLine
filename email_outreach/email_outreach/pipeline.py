"""
Stage 2 of the outreach pipeline.

Turns a ``places_<request_id>.csv`` (written by osmharvest, stage 1) into a
``contacts_<request_id>.csv`` by filling in emails for places that don't
already have one on their OSM tags but do list a website, by visiting that
website with WebsiteEmailScraper.

Design carried over from the original CSVEmailScraper script:
  - resumable via a JSON checkpoint next to the output file
  - each result is appended to disk immediately, so a crash loses at most
    the row in progress, never previously-saved rows
  - only rows that actually need a network visit (no OSM email tag, but a
    website is present) are scraped -- OSM-tag emails are free and are used
    as-is, which also means most jobs scrape far fewer than every place.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .scraper import WebsiteEmailScraper

logger = logging.getLogger("email_outreach.pipeline")

OUTPUT_COLUMNS = [
    "request_id",
    "category",
    "name",
    "distance_metres",
    "website",
    "source",
    "extracted_email",
]


def _progress_path(output_csv: Path) -> Path:
    return output_csv.with_name(output_csv.stem + ".progress.json")


def _load_progress(path: Path) -> dict:
    if not path.exists():
        return {"last_processed_index": -1}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Progress file %s is invalid, starting from beginning.", path)
        return {"last_processed_index": -1}


def _save_progress(path: Path, index: int) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps({"last_processed_index": index}, indent=2), encoding="utf-8")
    temp.replace(path)


def _append_row(output_csv: Path, row: dict) -> None:
    file_exists = output_csv.exists()
    pd.DataFrame([row], columns=OUTPUT_COLUMNS).to_csv(
        output_csv, mode="a", header=not file_exists, index=False
    )


def process_places_csv(
    request_id: str,
    places_csv_path: "str | Path",
    output_dir: "str | Path",
    *,
    max_places: Optional[int] = None,
    scraper: Optional[WebsiteEmailScraper] = None,
) -> Path:
    """
    Read places_<request_id>.csv and write contacts_<request_id>.csv into
    `output_dir`. Returns the path to the output CSV.

    For each place, nearest first (osmharvest already sorts by distance):
      - OSM tag already had an email  -> kept as-is, source="osm_tag"
      - no email, but a website exists -> scraped,   source="scraped_website"
      - neither                        -> skipped, no contactable email

    `max_places` caps how many nearest places are considered at all, which
    bounds the worst-case runtime of a single request's outreach run (each
    scraped site can take up to ~20s). Safe to re-call after an interruption:
    already-written rows are not reprocessed.
    """
    places_csv_path = Path(places_csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / f"contacts_{request_id}.csv"
    progress_file = _progress_path(output_csv)

    if not places_csv_path.exists():
        raise FileNotFoundError(f"Places CSV not found: {places_csv_path}")

    df = pd.read_csv(places_csv_path, dtype=str, keep_default_na=False)
    if max_places is not None:
        df = df.head(max_places)
    total_rows = len(df)

    progress = _load_progress(progress_file)
    start_index = progress.get("last_processed_index", -1) + 1

    if start_index >= total_rows:
        logger.info("Request %s: all %d place(s) already processed.", request_id, total_rows)
        if not output_csv.exists():
            pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(output_csv, index=False)
        return output_csv

    own_scraper = scraper is None
    if own_scraper:
        scraper = WebsiteEmailScraper()

    logger.info(
        "Request %s: processing places %d..%d of %d", request_id, start_index, total_rows - 1, total_rows
    )

    for index in range(start_index, total_rows):
        row = df.iloc[index]
        name = row.get("name", "")
        category = row.get("category", "")
        distance = row.get("distance_metres", "")
        website = (row.get("website") or "").strip()
        osm_email = (row.get("email") or "").strip()

        if osm_email:
            # OSM already had a contact email on this place's tags -- no need
            # to visit the site at all.
            for email in (part.strip() for part in osm_email.split(";")):
                if email:
                    _append_row(
                        output_csv,
                        {
                            "request_id": request_id,
                            "category": category,
                            "name": name,
                            "distance_metres": distance,
                            "website": website,
                            "source": "osm_tag",
                            "extracted_email": email,
                        },
                    )

        elif website:
            logger.info("Scraping %s (%s)", website, name or "unnamed")
            try:
                result = scraper.scrape(website)
            except Exception as error:  # noqa: BLE001 - one bad site must not kill the run
                logger.warning("Scraper exception for %s: %s", website, error)
                result = None

            if result is not None and result.status == "SUCCESS" and result.emails:
                for email in result.emails:
                    _append_row(
                        output_csv,
                        {
                            "request_id": request_id,
                            "category": category,
                            "name": name,
                            "distance_metres": distance,
                            "website": website,
                            "source": "scraped_website",
                            "extracted_email": email,
                        },
                    )
            elif result is not None:
                # Visible even on the "nothing found" path -- otherwise a
                # site that's blocked, errored, or just genuinely has no
                # published email all look identical from the outside: a
                # silent gap in the output CSV with no way to tell which.
                logger.info("  -> %s: %s", result.status, result.message)
            # else: scraper raised (already logged above as a warning).

        # else: no OSM email and no website -- nothing contactable found.

        _save_progress(progress_file, index)

    if not output_csv.exists():
        pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(output_csv, index=False)

    return output_csv


# ============================================================
# STANDALONE CLI (manual/debug use)
# ============================================================

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    parser = argparse.ArgumentParser(description="Scrape contact emails for one osmharvest request id.")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--places-csv", required=True, help="Path to places_<request_id>.csv")
    parser.add_argument("--output-dir", default="contacts", help="Directory to write contacts_<request_id>.csv into")
    parser.add_argument("--max-places", type=int, default=None)
    args = parser.parse_args()

    output_path = process_places_csv(
        request_id=args.request_id,
        places_csv_path=args.places_csv,
        output_dir=args.output_dir,
        max_places=args.max_places,
    )
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()