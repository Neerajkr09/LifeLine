"""Geometry: distance, bounding boxes, and circle subdivision.

The bounding-box helper matters for more than convenience. The Overpass docs
state that the bounding box filter performs faster than the ``around`` filter,
so querying a bbox and narrowing to the exact circle in Python puts less load
on a shared public server and makes a 504 less likely on every call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

EARTH_RADIUS_METRES: Final[float] = 6_371_008.8
_METRES_PER_DEGREE_LAT: Final[float] = 111_320.0


@dataclass(frozen=True, slots=True)
class Circle:
    """A search area: centre point plus radius in metres."""

    latitude: float
    longitude: float
    radius_metres: float

    def as_dict(self) -> dict[str, float]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_metres": self.radius_metres,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "Circle":
        return cls(
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            radius_metres=float(data["radius_metres"]),
        )


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """South, west, north, east — the order Overpass expects."""

    south: float
    west: float
    north: float
    east: float

    def as_overpass(self) -> str:
        return f"({self.south:.7f},{self.west:.7f},{self.north:.7f},{self.east:.7f})"


def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS-84 points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METRES * math.asin(math.sqrt(a))


def bounding_box(circle: Circle) -> BoundingBox:
    """Smallest lat/lon box enclosing the circle.

    The box is a superset of the circle, so results must still be filtered by
    :func:`haversine_metres` afterwards. That filter is required for
    correctness, not an optimisation.
    """
    d_lat = circle.radius_metres / _METRES_PER_DEGREE_LAT
    # Longitude degrees shrink towards the poles; guard the degenerate case.
    cos_lat = max(math.cos(math.radians(circle.latitude)), 1e-6)
    d_lon = circle.radius_metres / (_METRES_PER_DEGREE_LAT * cos_lat)
    return BoundingBox(
        south=max(circle.latitude - d_lat, -90.0),
        west=max(circle.longitude - d_lon, -180.0),
        north=min(circle.latitude + d_lat, 90.0),
        east=min(circle.longitude + d_lon, 180.0),
    )


def split_into_quadrants(circle: Circle) -> list[Circle]:
    """Cover ``circle`` with four smaller circles, one per quadrant.

    Each child is centred on a quadrant midpoint at offset R/2 and given radius
    R/sqrt(2), which is exactly the distance from that midpoint to the furthest
    corner of its quadrant. The union therefore covers the parent completely;
    a 1% margin absorbs floating-point and projection error.

    Children overlap, so the caller must deduplicate on (osm_type, osm_id).
    """
    radius = circle.radius_metres
    child_radius = radius / math.sqrt(2.0) * 1.01

    d_lat = (radius / 2.0) / _METRES_PER_DEGREE_LAT
    cos_lat = max(math.cos(math.radians(circle.latitude)), 1e-6)
    d_lon = (radius / 2.0) / (_METRES_PER_DEGREE_LAT * cos_lat)

    return [
        Circle(circle.latitude + lat_sign * d_lat,
               circle.longitude + lon_sign * d_lon,
               child_radius)
        for lat_sign in (-1, 1)
        for lon_sign in (-1, 1)
    ]
