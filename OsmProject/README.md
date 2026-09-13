# osmharvest

A resumable OpenStreetMap POI harvester. Give it a coordinate and a radius; it
finds colleges, universities, restaurants and pubs, stores them in SQLite, and
writes a per-request email file you can hand to the next stage of your pipeline.

Built for the case where the public Overpass servers are unreliable and the job
may need to run for days.

---

## Why it is shaped this way

Three observations drove the design.

**1. The 504s are load, not query size.** The same 5 km query returns 200 on one
instance and 504 on another minutes later, and the error text says
`Dispatcher_Client::request_read_and_idx::timeout. The server is probably too
busy`. That is a queueing failure on a shared machine, not your query being too
heavy. So the engineering effort goes into *retry, resume and rotation*, not
into shrinking requests below the point of usefulness.

**2. A raw `text/plain` POST body gets 406 from Apache.** The query must be
form-encoded as `data=<query>`. This is the single most common Overpass setup
mistake and produces a confusing "Not Acceptable" page.

**3. Bounding boxes are faster than `around`.** The Overpass documentation says
so explicitly. Querying a bbox and narrowing to the exact circle in Python puts
less load on the server on *every single call*, which directly reduces 504s.
The client-side distance filter is then mandatory for correctness, since a bbox
is a superset of the circle.

---

## Architecture

```
submit  ->  search_job row  ->  DISCOVERY task per category
                                      |
                                      v
                          bbox query, "out ids qt"  (tiny response)
                                      |
                                      v
                        N x DETAIL tasks of 200 ids each
                                      |
                                      v
                    id-batch query, "out center"  (bounded response)
                                      |
                            +---------+---------+
                            |                   |
                          200 OK              504 / 429
                            |                   |
                    parse + distance filter   backoff, rotate endpoint,
                            |                 retry; after 2 failures a
                    upsert by (type, id)      DISCOVERY task splits into
                            |                 4 quarter-sized tiles
                    rewrite export files
```

Every unit of work is a database row. The worker holds no state, so it can be
killed at any moment and restarted with no loss and no repeated work.

### The database is the cache

A task marked `DONE` is never re-run. Places are upserted on
`(osm_type, osm_id)`. Restarting a finished job costs zero requests. A separate
response cache would add a second source of truth for no benefit.

### Tables

| Table | Purpose |
|---|---|
| `search_job` | One row per request id: coordinates, radius, categories, status |
| `fetch_task` | The work queue: kind, batch, status, attempts, `next_retry_at` |
| `place` | Global place records, keyed by `(osm_type, osm_id)`, with `raw_tags` |
| `job_place` | Which places belong to which request, with distance and category |

`place` and `job_place` are separate on purpose: a pub found by three
overlapping searches is stored once and linked three times.

---

## Install

```bash
pip install -r requirements.txt          # requests + python-dotenv
```

`osmharvest/config.py` already defaults `OSMHARVEST_USER_AGENT` to this
project's real contact address, so there is nothing else to set for a normal
run. To point it at a different address instead (e.g. a different
deployment), either export the variable or drop a `.env` file next to this
README (see `.env.example`):

```bash
export OSMHARVEST_USER_AGENT="osm-harvester/1.0 (project; you@example.org)"
```

Windows PowerShell:

```powershell
$env:OSMHARVEST_USER_AGENT = "osm-harvester/1.0 (project; you@example.org)"
```

Setting a real contact address is not optional politeness — anonymous
high-volume clients are the first thing an Overpass operator blocks.

---

## Local testing, step by step

### 1. Run the offline test suite (no network)

```bash
python test_harvest.py
```

This builds a synthetic city of 1,383 POIs behind a fake, deliberately flaky
Overpass server and asserts:

- quadrant tiling leaves no gaps (480 sample points, 0 uncovered)
- the radius contract holds exactly (536 in, 422 correctly discarded)
- a forced discovery failure escalates to tiling and still completes
- a job killed after 3 tasks resumes and finishes
- re-running a complete job issues 0 requests
- emails deduplicate and semicolon-separated tags split into separate rows

### 2. Check the live servers before committing to a long run

```bash
python -m osmharvest doctor
```

Reports each endpoint's slot availability and sends one tiny real query.

### 3. Submit a small job first

```bash
python -m osmharvest submit --lat 51.5074 --lng -0.1278 --radius 1000 --categories pub
```

Prints an 8-digit request id. Then:

```bash
python -m osmharvest run --request-id 12345678
python -m osmharvest status --request-id 12345678
```

### 4. Scale up to the real job

```bash
python -m osmharvest submit --lat 51.5074 --lng -0.1278 --radius 5000
python -m osmharvest run --request-id 87654321 --follow
```

### 5. Prove resumability yourself

Start a run, press Ctrl+C halfway, then run the same command again. It picks up
exactly where it stopped. Press Ctrl+C twice to exit immediately.

---

## Commands

| Command | What it does |
|---|---|
| `submit` | Register a search, print its 8-digit request id |
| `run` | Work the queue. `--follow` keeps it alive and polling |
| `status` | Live per-category progress bars, counts, recent errors |
| `export` | Rewrite the output files from the database |
| `retry` | Return permanently-failed tasks to the queue |
| `doctor` | Endpoint health check plus one live test query |

Useful flags: `--batch-size`, `--min-interval`, `--query-timeout`,
`--endpoints`, `--max-tasks`, `--db`, `--export-dir`, `--log-file`.

---

## Output, per request id

```
exports/
  87654321/
    emails_87654321.csv       one row per (place, email), deduplicated
    emails_87654321.txt       bare address list, one per line
    places_87654321.csv       every place found
    places_87654321.geojson   openable in QGIS or geojson.io
    manifest_87654321.json    query params, counts, task states, timestamps
```

Files are **rewritten from the database after every batch**, atomically via a
temp file and rename. So you can read results while the job is still running,
and a reader never sees a half-written file. That is the answer to "I need the
results before day three" — they are there from the first minute.

---

## Running on a VPS

**systemd** (recommended):

```bash
sudo cp osmharvest.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now osmharvest
journalctl -u osmharvest -f
```

The worker traps SIGTERM and finishes its current task before exiting, so
`systemctl restart` never wastes an in-flight Overpass call.

**Or a plain shell supervisor:** `./run_worker.sh`

**Or just tmux:** `tmux new -s harvest` then `python -m osmharvest run --follow`

Back up `osmharvest.db` — it is the whole job. `scp` it anywhere and it works.

---

## Tuning for politeness

| Setting | Default | Notes |
|---|---|---|
| `OSMHARVEST_MIN_INTERVAL` | 3.0 s | Seconds between requests. Raise, never lower |
| `OSMHARVEST_BATCH_SIZE` | 200 | Ids per detail request |
| `OSMHARVEST_QUERY_TIMEOUT` | 180 | The `[timeout:]` value |
| `OSMHARVEST_ENDPOINT_COOLDOWN` | 120 s | Rest period after an endpoint fails |

Fair use on the public instances is roughly 10,000 requests and 1 GB per day.
A 5 km, 4-category job is about 20 requests. You have enormous headroom — but
only if you keep the interval sane.

---

## Licence

OSM data is ODbL. Attribution is a licence condition, not a courtesy, and is
written into every export. Any report, screenshot or downstream product must
carry "© OpenStreetMap contributors".
