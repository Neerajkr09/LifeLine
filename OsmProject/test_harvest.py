"""Offline integration test: a fake, deliberately flaky Overpass server."""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path

from osmharvest import config, store
from osmharvest.exporters import export_job
from osmharvest.geo import Circle, haversine_metres, bounding_box, split_into_quadrants
from osmharvest.overpass import OverpassClient, OverpassTransient
from osmharvest.parsing import extract_emails, parse_elements
from osmharvest.store import Store
from osmharvest.worker import Worker, plan_job, backoff_seconds

ORIGIN = (51.5074, -0.1278)
random.seed(7)

# --- build a synthetic city -------------------------------------------------
UNIVERSE: dict[tuple[str, int], dict] = {}
next_id = 1000
for amenity, count in [("pub", 450), ("restaurant", 900), ("college", 25), ("university", 8)]:
    for i in range(count):
        next_id += 1
        # scatter within ~7km so some land outside the 5km circle
        dlat = random.uniform(-0.063, 0.063)
        dlon = random.uniform(-0.10, 0.10)
        osm_type = "way" if i % 7 == 0 else "node"
        tags = {"amenity": amenity, "name": f"{amenity.title()} {i}"}
        if i % 3 == 0:
            tags["website"] = f"https://{amenity}{i}.example.co.uk"
        if i % 11 == 0:
            tags["email"] = f"info@{amenity}{i}.example.co.uk"
        if i % 47 == 0:
            tags["contact:email"] = f"a@{amenity}{i}.co.uk;bookings@{amenity}{i}.co.uk"
        if i % 5 == 0:
            tags["addr:housenumber"] = "12"
            tags["addr:street"] = "High Street"
            tags["addr:postcode"] = "SW1A 1AA"
        element = {"type": osm_type, "id": next_id, "tags": tags}
        lat, lon = ORIGIN[0] + dlat, ORIGIN[1] + dlon
        if osm_type == "node":
            element["lat"], element["lon"] = lat, lon
        else:
            element["center"] = {"lat": lat, "lon": lon}
        UNIVERSE[(osm_type, next_id)] = element

print(f"Synthetic universe: {len(UNIVERSE)} elements")
INSIDE = sum(
    1 for e in UNIVERSE.values()
    if haversine_metres(*ORIGIN, e.get("lat", (e.get("center") or {}).get("lat")),
                        e.get("lon", (e.get("center") or {}).get("lon"))) <= 5000
)
print(f"Truly within 5km: {INSIDE}")

# --- fake server ------------------------------------------------------------
CALLS = {"discovery": 0, "detail": 0, "failures": 0}
FAIL_PLAN = {"discovery_fail_for": set(), "detail_fail_once": set()}


def fake_execute(self, endpoint, query):
    self.request_count += 1
    self._last_request_at = 0.0

    if "out ids qt;" in query:
        CALLS["discovery"] += 1
        m = re.search(r'\^\((.*?)\)\$|"amenity"="(\w+)"', query)
        amenity = (m.group(1) or m.group(2)) if m else None
        # force failures for a chosen category to exercise tiling
        if amenity in FAIL_PLAN["discovery_fail_for"]:
            box = re.search(r"\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\)", query)
            south, west, north, east = map(float, box.groups())
            span = north - south
            # only the full-size query fails; the smaller tiles succeed
            if span > 0.07:
                CALLS["failures"] += 1
                raise OverpassTransient("HTTP 504 - simulated overload")
        box = re.search(r"\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\)", query)
        south, west, north, east = map(float, box.groups())
        elements = []
        for (t, i), e in UNIVERSE.items():
            if e["tags"]["amenity"] != amenity:
                continue
            lat = e.get("lat", (e.get("center") or {}).get("lat"))
            lon = e.get("lon", (e.get("center") or {}).get("lon"))
            if south <= lat <= north and west <= lon <= east:
                elements.append({"type": t, "id": i})
        return {"osm3s": {"timestamp_osm_base": "2026-08-18T06:00:00Z"},
                "elements": elements}

    CALLS["detail"] += 1
    refs = []
    for osm_type, ids in re.findall(r"(node|way|relation)\(id:([\d,]+)\);", query):
        refs += [(osm_type, int(x)) for x in ids.split(",")]
    key = tuple(sorted(refs))[:1]
    if key and key in FAIL_PLAN["detail_fail_once"]:
        FAIL_PLAN["detail_fail_once"].discard(key)
        CALLS["failures"] += 1
        raise OverpassTransient("HTTP 504 - simulated overload")
    return {"osm3s": {"timestamp_osm_base": "2026-08-18T06:00:00Z"},
            "elements": [UNIVERSE[r] for r in refs if r in UNIVERSE]}


OverpassClient._execute = fake_execute
OverpassClient._throttle = lambda self: None

# =========================================================================== #
print("\n" + "=" * 70)
print("TEST 1  geometry")
print("=" * 70)
c = Circle(51.5074, -0.1278, 5000)
b = bounding_box(c)
print(f"  bbox {b.as_overpass()}")
assert b.south < c.latitude < b.north and b.west < c.longitude < b.east
kids = split_into_quadrants(c)
assert len(kids) == 4
# every point of the parent circle must fall inside at least one child
misses = 0
for bearing in range(0, 360, 3):
    import math
    rad = math.radians(bearing)
    for frac in (0.25, 0.5, 0.75, 1.0):
        d = 5000 * frac
        plat = c.latitude + (d * math.cos(rad)) / 111320
        plon = c.longitude + (d * math.sin(rad)) / (111320 * math.cos(math.radians(c.latitude)))
        if not any(haversine_metres(k.latitude, k.longitude, plat, plon) <= k.radius_metres
                   for k in kids):
            misses += 1
print(f"  quadrant coverage: {misses} uncovered sample point(s) out of 480")
assert misses == 0, "tiling leaves gaps"
print(f"  child radius {kids[0].radius_metres:.0f}m (parent 5000m)")
print("  London->Paris haversine: %.1f km" % (haversine_metres(51.5074, -0.1278, 48.8566, 2.3522)/1000))

print("\n" + "=" * 70)
print("TEST 2  email parsing")
print("=" * 70)
cases = [
    ({"email": "A@B.CO.UK "}, ["a@b.co.uk"]),
    ({"contact:email": "x@y.com;z@y.com"}, ["x@y.com", "z@y.com"]),
    ({"email": "mailto:m@n.org"}, ["m@n.org"]),
    ({"email": "not-an-email"}, []),
    ({"email": "a@b.com", "contact:email": "a@b.com"}, ["a@b.com"]),
    ({}, []),
    ({"email": "  "}, []),
]
for tags, expected in cases:
    got = extract_emails(tags)
    assert got == expected, f"{tags} -> {got}, expected {expected}"
    print(f"  {str(tags)[:44]:<46} -> {got}")

print("\n" + "=" * 70)
print("TEST 3  backoff schedule")
print("=" * 70)
for attempt in range(1, 8):
    d = backoff_seconds(attempt)
    print(f"  attempt {attempt} -> {'DEAD' if d is None else f'{d:.0f}s'}")
assert backoff_seconds(7) is None

# =========================================================================== #
print("\n" + "=" * 70)
print("TEST 4  full job, with forced discovery failure -> tiling")
print("=" * 70)
for path in ("/tmp/h.db", "/tmp/h.db-wal", "/tmp/h.db-shm"):
    Path(path).unlink(missing_ok=True)
shutil.rmtree("/tmp/hexp", ignore_errors=True)

FAIL_PLAN["discovery_fail_for"] = {"restaurant"}

db = Store("/tmp/h.db")
rid = db.generate_request_id()
db.create_job(request_id=rid, latitude=ORIGIN[0], longitude=ORIGIN[1],
              radius_metres=5000.0, categories=list(config.DEFAULT_CATEGORIES))
plan_job(db, rid)
print(f"  request id {rid} (8 digits: {len(rid) == 8 and rid.isdigit()})")

client = OverpassClient()
worker = Worker(db, client, batch_size=200, export_dir=Path("/tmp/hexp"))
# monkeypatch sleeping so backoff doesn't stall the test
import osmharvest.worker as wmod
wmod.backoff_seconds = lambda attempts: None if attempts > 6 else 0.0
stats = worker.run(request_id=rid)

print(f"  discovery calls {CALLS['discovery']}, detail calls {CALLS['detail']}, "
      f"simulated failures {CALLS['failures']}")
print(f"  tasks done {stats.tasks_done}, dead {stats.tasks_dead}")
print(f"  places linked {stats.places_linked}, discarded (outside 5km) {stats.places_discarded}")
assert stats.tasks_dead == 0, "tasks died unexpectedly"
assert CALLS["failures"] > 0, "failure injection did not fire"

s = db.job_stats(rid)
print(f"  stored: {s['places']} places, {s['with_email']} with email, "
      f"{s['with_website']} with website")
assert s["places"] == INSIDE, f"expected {INSIDE} inside-radius places, got {s['places']}"
print(f"  radius contract holds: exactly {INSIDE} places within 5km")

rows = db.job_places(rid)
maxd = max(r["distance_metres"] for r in rows)
print(f"  furthest place {maxd:.0f}m (limit 5000m)")
assert maxd <= 5000.0

prog = db.category_progress(rid)
for r in prog:
    print(f"    {r['category']:<12} {r['done']}/{r['total']} tasks")
rest = [r for r in prog if r["category"] == "restaurant"][0]
assert rest["total"] > 5, "tiling should have created extra discovery tasks"
print(f"  restaurant was subdivided into extra tiles: {rest['total']} tasks total")

print("\n" + "=" * 70)
print("TEST 5  idempotency - rerun changes nothing")
print("=" * 70)
before = db.job_stats(rid)
c2 = CALLS["detail"]
plan_job(db, rid)
stats2 = Worker(db, client, export_dir=Path("/tmp/hexp")).run(request_id=rid)
after = db.job_stats(rid)
print(f"  places before {before['places']}, after {after['places']}")
print(f"  extra detail calls: {CALLS['detail'] - c2}, tasks run: {stats2.tasks_done}")
assert before == after and stats2.tasks_done == 0

print("\n" + "=" * 70)
print("TEST 6  crash recovery")
print("=" * 70)
db2 = Store("/tmp/h2.db") if False else None
Path("/tmp/h3.db").unlink(missing_ok=True)
db3 = Store("/tmp/h3.db")
rid3 = db3.generate_request_id()
db3.create_job(request_id=rid3, latitude=ORIGIN[0], longitude=ORIGIN[1],
               radius_metres=5000.0, categories=["pub"])
plan_job(db3, rid3)
w3 = Worker(db3, OverpassClient(), batch_size=50, export_dir=Path("/tmp/hexp3"))
w3.run(request_id=rid3, max_tasks=3)          # simulate being killed after 3 tasks
partial = db3.job_stats(rid3)["places"]
counts_mid = db3.task_counts(rid3)
print(f"  killed after 3 tasks: {partial} places stored, task states {counts_mid}")
assert partial > 0, "no partial results were persisted"
# simulate unclean shutdown leaving a RUNNING row
with db3.transaction() as conn:
    conn.execute("UPDATE fetch_task SET status='RUNNING' WHERE status='PENDING' "
                 "AND id=(SELECT MIN(id) FROM fetch_task WHERE status='PENDING')")
w3b = Worker(db3, OverpassClient(), batch_size=50, export_dir=Path("/tmp/hexp3"))
w3b.run(request_id=rid3)
final = db3.job_stats(rid3)["places"]
print(f"  resumed and completed: {final} places (job {db3.get_job(rid3)['status']})")
assert final > partial
assert db3.task_counts(rid3).get("RUNNING", 0) == 0

print("\n" + "=" * 70)
print("TEST 7  exports")
print("=" * 70)
paths = export_job(db, rid, Path("/tmp/hexp"))
import csv as _csv
with open(paths["emails_csv"], encoding="utf-8-sig") as fh:
    erows = list(_csv.DictReader(fh))
emails = [r["email"] for r in erows]
print(f"  emails_{rid}.csv: {len(erows)} row(s), all unique: {len(emails) == len(set(emails))}")
assert len(emails) == len(set(emails))
assert all(r["request_id"] == rid for r in erows)
multi = [r for r in erows if r["email"].startswith(("a@", "bookings@"))]
print(f"  semicolon-separated tag split into separate rows: {len(multi)} such row(s)")
assert multi
txt = paths["emails_txt"].read_text().strip().splitlines()
assert len(txt) == len(erows)
print(f"  emails_{rid}.txt: {len(txt)} line(s)")
manifest = json.loads(paths["manifest"].read_text())
print(f"  manifest counts: {manifest['counts']}")
assert manifest["counts"]["unique_emails"] == len(erows)
with open(paths["places_csv"], encoding="utf-8-sig") as fh:
    prows = list(_csv.DictReader(fh))
print(f"  places_{rid}.csv: {len(prows)} row(s)")
assert len(prows) == INSIDE
gj = json.loads(paths["places_geojson"].read_text())
print(f"  geojson: {len(gj['features'])} feature(s), attribution present: "
      f"{'OpenStreetMap' in gj['attribution']}")

print("\n" + "=" * 70)
print("TEST 8  second request id, separate files, shared place table")
print("=" * 70)
rid2 = db.generate_request_id()
db.create_job(request_id=rid2, latitude=51.5100, longitude=-0.1300,
              radius_metres=2000.0, categories=["pub"])
plan_job(db, rid2)
Worker(db, client, export_dir=Path("/tmp/hexp")).run(request_id=rid2)
s2 = db.job_stats(rid2)
print(f"  request {rid2}: {s2['places']} places, {s2['with_email']} with email")
assert rid != rid2
total_places = db._conn.execute("SELECT COUNT(*) FROM place").fetchone()[0]
total_links = db._conn.execute("SELECT COUNT(*) FROM job_place").fetchone()[0]
print(f"  place rows {total_places}, job_place links {total_links} "
      f"(links exceed places => shared rows, no duplication)")
assert total_links > total_places
for r in (rid, rid2):
    p = Path("/tmp/hexp") / r / f"emails_{r}.csv"
    print(f"  {p} exists: {p.exists()}")
    assert p.exists()

print("\n" + "=" * 70)
print("ALL TESTS PASSED")
print("=" * 70)
