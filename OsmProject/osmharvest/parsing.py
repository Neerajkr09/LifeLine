"""Turn raw Overpass elements into storable rows.

Two rules from the requirements are enforced here:

* A missing email or website never disqualifies a place. Absence of contact
  data is data.
* The raw tag dictionary is preserved verbatim, so a later question ("which of
  these are wheelchair accessible?") can be answered without re-fetching.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

from . import config
from .geo import haversine_metres

#: Deliberately permissive: OSM contains plenty of technically-invalid
#: addresses, and rejecting them loses real contacts. This only filters
#: obvious non-emails.
_EMAIL_PATTERN = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")

#: OSM stores multi-values separated by semicolons, occasionally by commas.
_MULTIVALUE_SPLIT = re.compile(r"[;,]")


def first_tag(tags: dict[str, str], keys: Sequence[str]) -> str | None:
    """First present, non-empty value among ``keys``."""
    for key in keys:
        value = (tags.get(key) or "").strip()
        if value:
            return value
    return None


def normalise_email(raw: str) -> str | None:
    """Clean a single email value, or return None if it is not one."""
    value = raw.strip().strip(".,;").lower()
    if value.startswith("mailto:"):
        value = value[7:].strip()
    return value if _EMAIL_PATTERN.match(value) else None


def extract_emails(tags: dict[str, str]) -> list[str]:
    """All distinct valid emails on an element, across every email-ish tag.

    A single tag can hold several addresses (``info@x.com;bookings@x.com``),
    so values are split before validation. Order is preserved for stability.
    """
    found: list[str] = []
    for key in config.EMAIL_KEYS:
        raw = (tags.get(key) or "").strip()
        if not raw:
            continue
        for part in _MULTIVALUE_SPLIT.split(raw):
            email = normalise_email(part)
            if email and email not in found:
                found.append(email)
    return found


def format_address(tags: dict[str, str]) -> str | None:
    """Assemble a readable address from ``addr:*`` tags."""
    house = tags.get("addr:housenumber") or tags.get("addr:housename")
    street = tags.get("addr:street")
    locality = (
        tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:suburb")
    )
    parts = [
        " ".join(p for p in (house, street) if p),
        locality,
        tags.get("addr:postcode"),
    ]
    address = ", ".join(p for p in parts if p)
    return address or None


def element_to_row(
    element: dict[str, Any],
    *,
    origin_lat: float,
    origin_lon: float,
) -> dict[str, Any] | None:
    """Flatten one Overpass element into a ``place`` row.

    Returns None for elements with no usable coordinates, since the distance
    filter that guarantees the radius contract cannot be applied to them.
    """
    osm_type = element.get("type")
    osm_id = element.get("id")
    if osm_type not in ("node", "way", "relation") or osm_id is None:
        return None

    tags: dict[str, str] = element.get("tags") or {}
    centre = element.get("center") or {}
    latitude = element.get("lat", centre.get("lat"))
    longitude = element.get("lon", centre.get("lon"))
    if latitude is None or longitude is None:
        return None

    emails = extract_emails(tags)

    return {
        "osm_type": osm_type,
        "osm_id": int(osm_id),
        "name": tags.get("name") or tags.get("operator") or tags.get("brand"),
        "amenity": tags.get("amenity"),
        "latitude": float(latitude),
        "longitude": float(longitude),
        # Multiple addresses are kept as a semicolon list; the exporter splits
        # them back out into one row per address.
        "email": ";".join(emails) if emails else None,
        "website": first_tag(tags, config.WEBSITE_KEYS),
        "phone": first_tag(tags, config.PHONE_KEYS),
        "address": format_address(tags),
        "postcode": tags.get("addr:postcode"),
        "opening_hours": tags.get("opening_hours"),
        "cuisine": tags.get("cuisine"),
        "operator": tags.get("operator"),
        "brand": tags.get("brand"),
        "raw_tags": json.dumps(tags, ensure_ascii=False, sort_keys=True),
        "distance_metres": round(
            haversine_metres(origin_lat, origin_lon, float(latitude), float(longitude)),
            1,
        ),
    }


def parse_elements(
    elements: Iterable[dict[str, Any]],
    *,
    origin_lat: float,
    origin_lon: float,
    radius_metres: float,
) -> tuple[list[dict[str, Any]], int]:
    """Parse elements and apply the exact radius filter.

    Returns ``(rows_inside_radius, count_discarded)``. The filter is mandatory:
    queries run against a bounding box, which is a superset of the circle, and
    overlapping tiles widen it further. Distance is recomputed from the user's
    original coordinates so the radius contract holds regardless of how the
    work was subdivided.
    """
    kept: list[dict[str, Any]] = []
    discarded = 0
    for element in elements:
        row = element_to_row(element, origin_lat=origin_lat, origin_lon=origin_lon)
        if row is None:
            discarded += 1
            continue
        if row["distance_metres"] > radius_metres:
            discarded += 1
            continue
        kept.append(row)
    return kept, discarded
