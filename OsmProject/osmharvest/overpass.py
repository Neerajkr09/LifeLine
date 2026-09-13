"""Overpass API client: correct encoding, endpoint rotation, honest errors.

Two failure modes dominate in practice and both are handled explicitly:

* **HTTP 406 Not Acceptable.** Overpass sits behind Apache, which rejects a raw
  request body sent as ``text/plain``. The query must be form-encoded as
  ``data=<query>``. This is the single most common setup mistake.

* **HTTP 200 with a ``remark``.** Overpass reports runtime failures (timeout,
  memory exhaustion) inside an otherwise successful response. Treating 200 as
  success silently produces empty results.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Final, Sequence

import requests

from . import config
from .geo import BoundingBox

LOGGER = logging.getLogger(__name__)


class OverpassError(RuntimeError):
    """Base class for Overpass failures."""


class OverpassTransient(OverpassError):
    """Worth retrying: server busy, rate limited, network blip, timeout."""


class OverpassPermanent(OverpassError):
    """Not worth retrying: the query itself is wrong."""


_ERROR_IN_HTML: Final[re.Pattern[str]] = re.compile(
    r"<strong[^>]*>Error</strong>\s*:(.*?)</p>", re.S | re.I
)


def _clean_html(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def extract_error_message(body: str) -> str:
    """Pull the human-readable error out of an Overpass HTML error page."""
    match = _ERROR_IN_HTML.search(body)
    if match:
        return _clean_html(match.group(1))[:400]
    return _clean_html(body)[:400]


class OverpassClient:
    """Serial, polite client that rotates across endpoints with cooldowns.

    Rotation is the main defence against the failure the user actually hit: the
    same query returning 200 on one instance and 504 on another within minutes.
    An endpoint that fails is rested rather than hammered.
    """

    def __init__(
        self,
        *,
        endpoints: Sequence[str] = config.DEFAULT_ENDPOINTS,
        query_timeout: int = config.QUERY_TIMEOUT,
        http_timeout: float = config.HTTP_TIMEOUT,
        min_interval: float = config.MIN_REQUEST_INTERVAL,
        cooldown: float = config.ENDPOINT_COOLDOWN,
        session: requests.Session | None = None,
    ) -> None:
        if not endpoints:
            raise ValueError("At least one endpoint is required")
        self.endpoints = tuple(endpoints)
        self.query_timeout = query_timeout
        self._http_timeout = http_timeout
        self._min_interval = min_interval
        self._cooldown = cooldown
        self._blocked_until: dict[str, float] = {}
        self._last_request_at: float | None = None
        self._cursor = 0
        self._session = session or self._build_session()
        self.request_count = 0
        self.data_timestamp: str | None = None

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "application/json,text/*;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        # Deliberately no urllib3 Retry: retries are owned by the task queue,
        # which persists attempt counts across process restarts. Retrying in
        # two places at once multiplies load on a shared public server.
        return session

    def __enter__(self) -> "OverpassClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    # -- endpoint selection ------------------------------------------------- #

    def _available_endpoints(self) -> list[str]:
        now = time.monotonic()
        ready = [e for e in self.endpoints if self._blocked_until.get(e, 0.0) <= now]
        if ready:
            # Round-robin so load spreads instead of always hitting the first.
            start = self._cursor % len(ready)
            return ready[start:] + ready[:start]
        # Everything is cooling down; use whichever frees up soonest.
        return [min(self.endpoints, key=lambda e: self._blocked_until.get(e, 0.0))]

    def _penalise(self, endpoint: str) -> None:
        self._blocked_until[endpoint] = time.monotonic() + self._cooldown
        LOGGER.warning(
            "Resting %s for %.0fs", _short(endpoint), self._cooldown
        )

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._min_interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    # -- public API --------------------------------------------------------- #

    def status(self, endpoint: str | None = None) -> str:
        """Fetch ``/api/status`` — slot availability and rate limit."""
        target = (endpoint or self.endpoints[0]).replace(
            "/api/interpreter", "/api/status"
        )
        response = self._session.get(target, timeout=30)
        response.raise_for_status()
        return response.text.strip()

    def run(self, query: str) -> dict[str, Any]:
        """Execute a query, trying each available endpoint once.

        Raises :class:`OverpassTransient` if every endpoint failed in a way that
        is worth retrying later, or :class:`OverpassPermanent` immediately if
        the query itself is malformed.
        """
        last_error: OverpassError | None = None
        for endpoint in self._available_endpoints():
            self._cursor += 1
            try:
                return self._execute(endpoint, query)
            except OverpassPermanent:
                raise  # a bad query is bad everywhere; fail fast
            except OverpassTransient as exc:
                LOGGER.warning("%s: %s", _short(endpoint), _first_line(str(exc)))
                self._penalise(endpoint)
                last_error = exc
        raise last_error or OverpassTransient("All endpoints unavailable")

    def _execute(self, endpoint: str, query: str) -> dict[str, Any]:
        self._throttle()
        LOGGER.debug("POST %s\n%s", endpoint, query)
        try:
            response = self._session.post(
                endpoint,
                # Form-encoded, NOT a raw text/plain body. Apache answers a raw
                # body with 406 Not Acceptable.
                data={"data": query},
                timeout=self._http_timeout,
            )
        except requests.Timeout as exc:
            self._last_request_at = time.monotonic()
            raise OverpassTransient(f"Socket timeout after {self._http_timeout}s") from exc
        except requests.RequestException as exc:
            self._last_request_at = time.monotonic()
            raise OverpassTransient(f"Network error: {exc}") from exc

        self._last_request_at = time.monotonic()
        self.request_count += 1
        status = response.status_code

        if status == 200:
            return self._parse(response)
        if status == 400:
            raise OverpassPermanent(
                f"HTTP 400 - malformed query: {extract_error_message(response.text)}"
            )
        if status == 429:
            raise OverpassTransient(
                "HTTP 429 - per-IP slot limit reached; check /api/status"
            )
        if status == 504:
            raise OverpassTransient(
                f"HTTP 504 - {extract_error_message(response.text) or 'server busy'}"
            )
        if status in (406, 415):
            # Should be unreachable now the encoding is right, but if a mirror
            # is fussier, say so plainly instead of retrying forever.
            raise OverpassPermanent(
                f"HTTP {status} - endpoint rejected the request encoding. "
                f"The query must be form-encoded as data=<query>."
            )
        if 500 <= status < 600:
            raise OverpassTransient(f"HTTP {status} - {extract_error_message(response.text)}")
        raise OverpassPermanent(f"HTTP {status} - {extract_error_message(response.text)}")

    def _parse(self, response: requests.Response) -> dict[str, Any]:
        text = response.text
        if not text.lstrip().startswith("{"):
            # A 200 carrying an HTML error page. Overpass really does this.
            raise OverpassTransient(
                f"HTTP 200 but body was not JSON: {extract_error_message(text)}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OverpassTransient(f"Malformed JSON: {text[:200]}") from exc

        remark = str(payload.get("remark") or "").strip()
        if remark:
            lowered = remark.lower()
            if "error" in lowered or "timed out" in lowered or "out of memory" in lowered:
                raise OverpassTransient(f"HTTP 200 with runtime error: {remark}")
            LOGGER.info("Server remark: %s", remark)

        timestamp = (payload.get("osm3s") or {}).get("timestamp_osm_base")
        if timestamp:
            self.data_timestamp = timestamp
        return payload


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #


def build_discovery_query(
    *,
    filter_expression: str,
    box: BoundingBox,
    query_timeout: int,
) -> str:
    """Phase 1: element type and id only, over a bounding box.

    ``out ids`` is the cheapest output Overpass offers — no tags, no geometry —
    so a category with thousands of hits still returns a small response. The
    bbox filter is documented as faster than ``around``. ``qt`` sorts by
    quadtile, which is cheaper for the server to produce than sorting by id and
    is still deterministic, so it remains a valid pagination cursor.
    """
    return (
        f"[out:json][timeout:{query_timeout}];\n"
        f"nwr{filter_expression}{box.as_overpass()};\n"
        f"out ids qt;"
    )


def build_detail_query(
    *,
    refs: Sequence[tuple[str, int]],
    query_timeout: int,
) -> str:
    """Phase 2: full tags plus a representative point, for one batch of ids.

    Ids are bundled into one statement per element type, which the Overpass
    docs recommend over issuing them individually. ``out center`` returns
    coordinates for nodes and a centre point for ways and relations.
    """
    grouped: dict[str, list[int]] = {"node": [], "way": [], "relation": []}
    for osm_type, osm_id in refs:
        grouped.setdefault(osm_type, []).append(osm_id)

    statements = [
        f"  {osm_type}(id:{','.join(str(i) for i in sorted(set(ids)))});"
        for osm_type, ids in grouped.items()
        if ids
    ]
    if not statements:
        raise ValueError("Cannot build a detail query for an empty batch")

    body = "\n".join(statements)
    return f"[out:json][timeout:{query_timeout}];\n(\n{body}\n);\nout center;"


def _short(endpoint: str) -> str:
    return endpoint.split("//", 1)[-1].split("/", 1)[0]


def _first_line(text: str) -> str:
    return text.splitlines()[0] if text else text
