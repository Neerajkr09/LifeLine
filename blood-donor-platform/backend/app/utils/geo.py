"""
Point-to-point distance helper.

MongoDB's $geoNear (used for the donor matching *list*) computes distance as
part of an aggregation over many documents. Elsewhere -- e.g. deciding
whether one specific donor is allowed to view one specific request's detail
and document -- we already have both GeoJSON points in hand after a normal
find_one(), so a plain Haversine calculation is simpler than round-tripping
through another aggregation.
"""
import math
from typing import Optional


def haversine_km(point_a: Optional[dict], point_b: Optional[dict]) -> Optional[float]:
    """
    Great-circle distance in kilometres between two GeoJSON Points
    ({"type": "Point", "coordinates": [lng, lat]}). Returns None if either
    point is missing, so callers can decide how to treat "unknown distance"
    (typically: don't block access, just skip the radius check).
    """
    if not point_a or not point_b:
        return None
    try:
        lon1, lat1 = point_a["coordinates"]
        lon2, lat2 = point_b["coordinates"]
    except (KeyError, ValueError, TypeError):
        return None

    r = 6371.0088  # mean Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))
