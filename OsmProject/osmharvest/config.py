"""Configuration: endpoints, categories, and tuning knobs.

Everything here is a default. The CLI can override the ones that matter, and
``OSMHARVEST_*`` environment variables override the rest, so a VPS deployment
never needs the source edited.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

try:
    # Optional convenience: if python-dotenv is installed and a .env file
    # exists next to the project, load it before reading os.environ below.
    # Nothing here breaks if python-dotenv isn't installed -- the OSMHARVEST_*
    # environment variables (and the baked-in defaults) still work.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

#: Public Overpass instances, tried in order with per-endpoint cooldown.
#: Ordered kumi-first because the user's own testing showed it answering
#: queries that overpass-api.de rejected under load.
DEFAULT_ENDPOINTS: Final[tuple[str, ...]] = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
)


def _env(name: str, default: str) -> str:
    return os.environ.get(f"OSMHARVEST_{name}", default)


#: Identify the client. This default already points at the project's real
#: contact address, so a deployment works correctly with zero setup -- but it
#: can still be overridden per-environment via OSMHARVEST_USER_AGENT (or a
#: .env file) without touching source.
USER_AGENT: Final[str] = _env(
    "USER_AGENT",
    "osm-harvester/1.0 (blood-donor-outreach-platform; contact: krneeraj.0509@gmail.com)",
)

# --------------------------------------------------------------------------- #
# Request behaviour
# --------------------------------------------------------------------------- #

#: Seconds to wait between requests. Overpass allows ~2 concurrent slots per IP;
#: one serial request every few seconds sits comfortably inside fair use.
MIN_REQUEST_INTERVAL: Final[float] = float(_env("MIN_INTERVAL", "3.0"))

#: HTTP socket timeout. Must exceed the in-query [timeout:] setting.
HTTP_TIMEOUT: Final[float] = float(_env("HTTP_TIMEOUT", "300"))

#: Value for the Overpass ``[timeout:N]`` setting, in seconds.
QUERY_TIMEOUT: Final[int] = int(_env("QUERY_TIMEOUT", "180"))

#: How long to rest an endpoint after it fails, in seconds.
ENDPOINT_COOLDOWN: Final[float] = float(_env("ENDPOINT_COOLDOWN", "120"))

#: Retry schedule in seconds, indexed by attempt number. Beyond the end of the
#: list a task is marked DEAD and reported rather than retried forever.
RETRY_BACKOFF_SECONDS: Final[tuple[int, ...]] = (30, 60, 120, 300, 600, 1800)

#: Random jitter added to every backoff, as a fraction of the delay. Stops
#: several workers from waking up in lockstep.
RETRY_JITTER: Final[float] = 0.25

#: OSM ids per detail request. 200 keeps responses to a few hundred KB.
DEFAULT_BATCH_SIZE: Final[int] = int(_env("BATCH_SIZE", "200"))

#: A discovery query that fails this many times is split into four sub-tiles
#: instead of being retried at the same size.
DISCOVERY_ATTEMPTS_BEFORE_TILING: Final[int] = 2

#: Stop subdividing below this radius; past here the problem is not query size.
MIN_TILE_RADIUS_METRES: Final[float] = 400.0

MAX_RADIUS_METRES: Final[float] = 50_000.0

ATTRIBUTION: Final[str] = "Data (c) OpenStreetMap contributors, ODbL 1.0"

# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #

_SAFE_TAG_TOKEN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True, slots=True)
class Category:
    """A group of OSM tag values harvested as one logical unit of work."""

    key: str
    label: str
    tag_key: str
    tag_values: tuple[str, ...]

    def __post_init__(self) -> None:
        # These strings are interpolated into a query, so validate rather than
        # trust. A value like 'pub"];out meta;//' would otherwise be injection.
        if not _SAFE_TAG_TOKEN.match(self.tag_key):
            raise ValueError(f"Unsafe tag key: {self.tag_key!r}")
        for value in self.tag_values:
            if not _SAFE_TAG_TOKEN.match(value):
                raise ValueError(f"Unsafe tag value: {value!r}")

    @property
    def filter_expression(self) -> str:
        """Anchored regex filter, e.g. ``["amenity"~"^(pub|bar)$"]``."""
        if len(self.tag_values) == 1:
            return f'["{self.tag_key}"="{self.tag_values[0]}"]'
        return f'["{self.tag_key}"~"^({"|".join(self.tag_values)})$"]'


#: Colleges and universities are deliberately separate categories: they are
#: separate units of work, separate retry state, and separate progress lines.
CATEGORIES: Final[dict[str, Category]] = {
    "college": Category("college", "College", "amenity", ("college",)),
    "university": Category("university", "University", "amenity", ("university",)),
    "restaurant": Category("restaurant", "Restaurant", "amenity", ("restaurant",)),
    "pub": Category("pub", "Pub", "amenity", ("pub",)),
    # Opt-in extras
    "bar": Category("bar", "Bar", "amenity", ("bar",)),
    "cafe": Category("cafe", "Cafe", "amenity", ("cafe",)),
    "fast_food": Category("fast_food", "Fast food", "amenity", ("fast_food",)),
    "school": Category("school", "School", "amenity", ("school",)),
}

DEFAULT_CATEGORIES: Final[tuple[str, ...]] = (
    "college",
    "university",
    "restaurant",
    "pub",
)

# --------------------------------------------------------------------------- #
# Tag extraction
# --------------------------------------------------------------------------- #

WEBSITE_KEYS: Final[tuple[str, ...]] = (
    "website",
    "contact:website",
    "url",
    "contact:url",
    "operator:website",
    "website:official",
)
EMAIL_KEYS: Final[tuple[str, ...]] = (
    "email",
    "contact:email",
    "operator:email",
)
PHONE_KEYS: Final[tuple[str, ...]] = (
    "phone",
    "contact:phone",
    "contact:mobile",
    "telephone",
)
