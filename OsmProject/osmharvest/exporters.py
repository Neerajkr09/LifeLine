"""Export a job's results to files, keyed by request id.

Exports are rewritten from the database rather than appended to. Rewriting is
idempotent: run it after every batch, after a crash, or a year later, and the
file is correct and duplicate-free. Appending would require the writer to know
what it had already written, which is exactly the state that does not survive a
restart.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .config import ATTRIBUTION

EMAIL_COLUMNS: tuple[str, ...] = (
    "request_id",
    "email",
    "category",
    "name",
    "website",
    "phone",
    "address",
    "postcode",
    "latitude",
    "longitude",
    "distance_metres",
    "osm_type",
    "osm_id",
    "osm_url",
)

PLACE_COLUMNS: tuple[str, ...] = (
    "request_id",
    "category",
    "name",
    "distance_metres",
    "email",
    "website",
    "phone",
    "address",
    "postcode",
    "opening_hours",
    "cuisine",
    "operator",
    "brand",
    "amenity",
    "latitude",
    "longitude",
    "osm_type",
    "osm_id",
    "osm_url",
)


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def _write_csv(path: Path, columns: Sequence[str], rows: list[dict[str, Any]]) -> None:
    """Write atomically: a reader never sees a half-written file.

    This matters because the whole point of exporting after every batch is that
    someone will be reading these files while the worker is still running.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def build_email_rows(request_id: str, places: list[Any]) -> list[dict[str, Any]]:
    """One row per (place, email) pair, deduplicated by email address.

    A place holding ``info@x.com;bookings@x.com`` becomes two rows. Where the
    same address appears at several places — a chain's head office, typically —
    the nearest occurrence wins, because ``places`` arrives sorted by distance.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for place in places:
        raw = (place["email"] or "").strip()
        if not raw:
            continue
        for email in (part.strip() for part in raw.split(";")):
            if not email or email in seen:
                continue
            seen.add(email)
            rows.append(
                {
                    "request_id": request_id,
                    "email": email,
                    "category": place["category"],
                    "name": place["name"],
                    "website": place["website"],
                    "phone": place["phone"],
                    "address": place["address"],
                    "postcode": place["postcode"],
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "distance_metres": place["distance_metres"],
                    "osm_type": place["osm_type"],
                    "osm_id": place["osm_id"],
                    "osm_url": osm_url(place["osm_type"], place["osm_id"]),
                }
            )
    return rows


def build_place_rows(request_id: str, places: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "request_id": request_id,
            **{
                key: place[key]
                for key in place.keys()
                if key in PLACE_COLUMNS and key != "request_id"
            },
            "osm_url": osm_url(place["osm_type"], place["osm_id"]),
        }
        for place in places
    ]


def export_job(db: Any, request_id: str, export_dir: Path = Path("exports")) -> dict[str, Path]:
    """Write every artefact for one request id. Returns the paths written."""
    job = db.get_job(request_id)
    if job is None:
        raise KeyError(f"No such request id: {request_id}")

    places = db.job_places(request_id)
    stats = db.job_stats(request_id)
    directory = export_dir / request_id
    directory.mkdir(parents=True, exist_ok=True)

    email_rows = build_email_rows(request_id, places)
    place_rows = build_place_rows(request_id, places)

    paths = {
        "emails_csv": directory / f"emails_{request_id}.csv",
        "emails_txt": directory / f"emails_{request_id}.txt",
        "places_csv": directory / f"places_{request_id}.csv",
        "places_geojson": directory / f"places_{request_id}.geojson",
        "manifest": directory / f"manifest_{request_id}.json",
    }

    _write_csv(paths["emails_csv"], EMAIL_COLUMNS, email_rows)
    _write_csv(paths["places_csv"], PLACE_COLUMNS, place_rows)

    # A bare address list, for piping into whatever comes next.
    plain = paths["emails_txt"].with_suffix(".txt.tmp")
    plain.write_text(
        "\n".join(row["email"] for row in email_rows) + ("\n" if email_rows else ""),
        encoding="utf-8",
    )
    plain.replace(paths["emails_txt"])

    _write_geojson(paths["places_geojson"], place_rows)

    manifest = {
        "request_id": request_id,
        "attribution": ATTRIBUTION,
        "query": {
            "latitude": job["latitude"],
            "longitude": job["longitude"],
            "radius_metres": job["radius_metres"],
            "categories": json.loads(job["categories"]),
        },
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "places": stats.get("places", 0),
            "unique_emails": len(email_rows),
            "places_with_email": stats.get("with_email", 0),
            "places_with_website": stats.get("with_website", 0),
            "places_with_phone": stats.get("with_phone", 0),
        },
        "tasks": db.task_counts(request_id),
        "files": {key: path.name for key, path in paths.items() if key != "manifest"},
    }
    temporary = paths["manifest"].with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(paths["manifest"])

    return paths


def _write_geojson(path: Path, place_rows: list[dict[str, Any]]) -> None:
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },
            "properties": {
                key: value
                for key, value in row.items()
                if key not in ("latitude", "longitude") and value is not None
            },
        }
        for row in place_rows
        if row.get("latitude") is not None and row.get("longitude") is not None
    ]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "attribution": ATTRIBUTION,
                "features": features,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
