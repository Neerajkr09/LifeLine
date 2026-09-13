# Blood Donor Outreach Platform — Integration Guide

> **On Windows / VS Code?** Skip straight to `WINDOWS_SETUP.md` in this same
> folder — it has the PowerShell-native, copy-pasteable version of everything
> below. This file's "Setup, in order" section uses bash/Linux commands.

This merges three previously-separate projects into one automated pipeline:
recipient submits a request → nearby colleges/universities/restaurants/pubs
are found via OpenStreetMap → a contact email is compiled for each → a CSV is
ready for you (or the recipient) to reach out from — no manual steps between
"request submitted" and "CSV ready."

```
blood-donor-outreach-platform/
├── blood-donor-platform/     FastAPI + MongoDB backend + React frontend (yours, lightly patched)
├── OsmProject/                Resumable OSM/Overpass harvester (yours, lightly patched)
├── email_outreach/            NEW — your Scraper.py + CSV processor, refactored into a package
├── outreach_orchestrator/     NEW — the glue: watches for completed OSM jobs, triggers the scrape
└── README_INTEGRATION.md      this file
```

## What actually happens, end to end

```
1. Recipient submits a blood request (lat/lng required on the form already)
        |
        v
2. FastAPI backend inserts the request, then makes ONE fast local SQLite
   write into osmharvest.db (no network call -- sub-millisecond). Response
   to the recipient is not delayed by anything below this line.
        |
        v
3. osmharvest worker (a separate long-running process you already had --
   `python -m osmharvest run --follow`) picks the job up, queries Overpass
   with proper rate-limiting/retry/backoff, and writes
   OsmProject/exports/<osm_id>/places_<osm_id>.csv as it goes.
        |
        v
4. outreach_orchestrator (NEW, also long-running) polls osmharvest.db. The
   moment a job's status flips to COMPLETED / COMPLETED_WITH_ERRORS, it:
     - re-exports the CSVs to be safe
     - runs email_outreach on places_<osm_id>.csv:
         · a place with an OSM email tag -> used as-is, no network call
         · a place with a website but no email tag -> scraped
         · a place with neither -> skipped
     - writes contacts_<osm_id>.csv
     - updates the blood request in MongoDB: outreach.status = "ready"
        |
        v
5. GET /api/v1/blood-requests/{id}/outreach          -> progress/status
   GET /api/v1/blood-requests/{id}/outreach/contacts  -> the CSV, once ready
```

Three processes run continuously in production: the FastAPI backend, the
`osmharvest` worker, and `outreach_orchestrator`. All three already follow
the same pattern you'd built into OsmProject (systemd units + a plain
`run_*.sh` fallback), so nothing here introduces a new deployment model.

## What didn't change

Every existing feature and validation in `blood-donor-platform` works
exactly as it did before this integration: auth/JWT, OTP verification,
blood-group compatibility matching, the donor-rejection auto-ban threshold,
rate limiting, hospital-document upload validation, and the existing
5km **donor-matching** radius (`DONOR_MATCH_RADIUS_KM` in
`blood_request_controller.py`) that decides which donors see a request —
that's a separate, older setting from the new outreach radius below and I
left it untouched.

Confirmed, not just assumed: I built the full FastAPI app in this sandbox
and it registers all of the platform's original routes plus exactly two new
ones (`.../outreach` and `.../outreach/contacts`) — nothing was replaced or
restructured, only added to.

## Email filtering: your updated exclusions are already in

`email_outreach/scraper.py` is your pasted scraper carried over class-for-
class, so it already rejects everything you listed, before this
conversation even mentioned it:
- any address at `sentry-next.wixpress.com`, `sentry.wixpress.com`, or the
  parent `wixpress.com` (including hashy Sentry addresses like
  `605a7bae...@sentry-next.wixpress.com` — caught by domain, not local-part,
  so the random hash in front doesn't matter)
- any local-part matching `noreply` / `no-reply` / `no_reply` /
  `donotreply` / `do-not-reply` / `do_not_reply` (and `postmaster`,
  `mailer-daemon`, a few others)

I re-verified this just now against your exact examples plus a real address
to confirm it isn't over-blocking:

```
605a7baede844d278b89dc95ae0a9123@sentry-next.wixpress.com -> False (rejected)
someone@sentry.wixpress.com                                -> False (rejected)
anything@wixpress.com                                       -> False (rejected)
noreply@somecollege.edu                                     -> False (rejected)
no-reply@somepub.com                                         -> False (rejected)
donotreply@somerestaurant.com                                -> False (rejected)
admissions@somecollege.edu                                  -> True  (kept)
```

## Setup, in order

### 1. MongoDB, as before
No change to how you run Mongo.

### 2. OsmProject
```bash
cd OsmProject
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # requests + python-dotenv
python test_harvest.py                 # optional, offline sanity check
python -m osmharvest doctor            # confirms Overpass endpoints are reachable
python -m osmharvest run --follow --log-file logs/worker.log &
```
`OSMHARVEST_USER_AGENT` now defaults to
`namansrivastava001.jnp@gmail.com` automatically — nothing to export by
hand. Override it via `.env` (see `.env.example`) if you ever need to.

### 3. email_outreach
```bash
cd ../email_outreach
python -m venv .venv && source .venv/bin/activate
pip install -e .
sudo apt-get install -y chromium chromium-driver   # needs a real browser
```

### 4. outreach_orchestrator
```bash
cd ../outreach_orchestrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # also installs osmharvest + email_outreach, editable
python orchestrator.py \
  --mongo-uri mongodb://localhost:27017 \
  --mongo-db blood_donor_platform \
  --osm-db ../OsmProject/osmharvest.db \
  --export-dir ../OsmProject/exports \
  --contacts-dir ./contacts \
  --max-places 40 \
  --poll 30 &
```

### 5. Backend
```bash
cd ../blood-donor-platform/backend
python -m venv .venv && source .venv/bin/activate
cp .env.example .env        # fill in MONGO_URI etc., as before
pip install -r requirements.txt   # now also installs osmharvest + email_outreach, editable
uvicorn app.main:app --reload
```

For steps 3–5 to import `osmharvest`/`email_outreach` as installed packages,
keep the four top-level folders as siblings (as in this zip) — the
`-e ../../OsmProject` / `-e ../email_outreach` paths in each
`requirements.txt` are relative to that layout.

On a VPS, install `OsmProject/osmharvest.service` and
`outreach_orchestrator/outreach-worker.service` under systemd (both already
provided) alongside your existing backend service.

## What I changed in your existing projects

**blood-donor-platform/backend** — additive only, nothing existing was
restructured:
- `app/models/blood_request_model.py` — new `outreach` sub-document on every
  request (`status`, `osm_request_id`, `contacts_csv_path`, `contact_count`,
  `error`, timestamps), new `OutreachStatus` enum.
- `app/services/outreach_service.py` — new file. Submits the OSM job;
  wrapped so a failure here (bad DB path, disk issue, etc.) **never** blocks
  or fails blood-request creation, since that's the life-critical path.
- `app/controllers/blood_request_controller.py` — three lines added to
  `create_blood_request` (submit + persist the outreach state), plus two new
  read-only controller functions.
- `app/routes/blood_request_routes.py` — two new endpoints, both
  recipient-owner-only, matching the existing `/document` endpoint's access
  pattern.
- `app/utils/serializers.py`, `app/schemas/blood_request_schema.py` — one
  new serializer + response schema.
- `app/core/config.py`, `.env.example` — new settings:
  `OUTREACH_ENABLED`, `OUTREACH_RADIUS_METRES` (default 3000m),
  `OUTREACH_CATEGORIES` (default matches your ask: college, university,
  restaurant, pub), `OSM_DB_PATH`.

**OsmProject** — three small changes, core harvester logic untouched:
- `osmharvest/config.py` — default `USER_AGENT` now bakes in your real
  address instead of the `you@example.ac.uk` placeholder, and optionally
  loads a `.env` file (added `python-dotenv` to `requirements.txt`).
- `osmharvest.service`, `README.md`, `.env.example` — same address reflected
  consistently.
- `pyproject.toml` (new) — makes it `pip install -e`-able so the backend and
  orchestrator can import it directly, instead of `sys.path` hacks.

**email_outreach** — new package, but the actual scraping/filtering logic is
your pasted code verbatim (class-for-class), just split into an importable
module instead of a script that reads `input.csv`. The one behavioral
addition: `pipeline.py` now skips the browser entirely for any place OSM
already gave an email tag for, so most jobs scrape a fraction of the places
they find.

## Defaults I picked (all easy to change)

| Setting | Default | Where | Why |
|---|---|---|---|
| Search radius | 5000m | `OUTREACH_RADIUS_METRES` (backend `.env`) | Matches your spec. OsmProject's own README notes a 5km/4-category job is only ~20 Overpass requests — well inside fair-use and normally done in well under a minute of Overpass time, not the multi-day worst case that README describes for large or repeatedly-504ing jobs |
| Categories | college, university, restaurant, pub | `OUTREACH_CATEGORIES` | Exactly what you described |
| Places scraped per request | nearest 40 | `--max-places` (orchestrator) | Bounds worst-case runtime (~20s/site) to a predictable window regardless of how many places a radius returns. At 5km you may find more places with a website-but-no-email than at 3km, so raise this if you want every one of them attempted rather than just the nearest 40 |
| Poll interval | 30s | `--poll` (orchestrator) | OSM jobs take minutes, not seconds — no benefit to polling faster |

### A note on "parallel"

Outreach runs **in parallel with the rest of the platform** in the sense
that matters: it's a background process, so it never delays the recipient's
request submission, and it has zero effect on login, OTP, donor matching,
rejections, bans, rate limiting, or anything else already in the app — those
all continue to run exactly as before, untouched.

What it deliberately does **not** do is fire concurrent Overpass requests.
osmharvest processes one Overpass call at a time with a mandatory pause
between them (`OSMHARVEST_MIN_INTERVAL`, 3s by default) — that's not a
limitation I introduced, it's the existing politeness/rate-limit design in
OsmProject, and it's why the User-Agent doesn't get blocked. All four
categories (college, university, restaurant, pub) are queued at once, but
the single worker still works through them one request at a time.

## Things you'll need to verify on your own machine

I don't have network access to Overpass or a Chrome binary in this sandbox,
so I could not run a real end-to-end harvest or a real browser scrape. What
I *did* verify here, with real (not hand-waved) tests:

- OsmProject's own offline test suite passes unmodified.
- `email_outreach.pipeline` correctly merges OSM-tag emails with scraped
  emails, correctly skips places with neither, and correctly resumes
  without re-scraping already-processed rows (tested against a synthetic
  places CSV with a mocked scraper).
- `email_outreach.scraper`'s business-email filter (junk/system-address
  rejection) behaves correctly against a set of real and edge-case
  addresses.
- `outreach_orchestrator.process_once` correctly detects a completed OSM
  job, claims it, runs the real pipeline, and writes back to Mongo — tested
  against a real SQLite `osmharvest.db` and a `mongomock` in-memory Mongo.
- `outreach_orchestrator.process_once` correctly leaves an
  in-progress job untouched.
- The full FastAPI app **builds successfully** with both new routes
  registered (`/blood-requests/{id}/outreach` and `.../outreach/contacts`),
  and `outreach_service.submit_outreach_job` was run for real against a
  temp SQLite file and produced a correct, real osmharvest job row.

What's still worth trying yourself before relying on this in production:
a real Overpass run against your actual `OSMHARVEST_USER_AGENT`, and a real
Selenium scrape against a couple of live sites near you, to confirm Chrome
is set up correctly on your deployment machine.

## One deliberate scope decision

This pipeline **compiles a CSV of contact emails — it does not send anything
to them.** I kept it that way on purpose: harvesting publicly-listed contact
addresses to build a reach-out list is one thing, but automatically emailing
them at scale on every request is a different feature with its own
considerations (anti-spam law, consent/opt-out, per-domain rate limits,
what the message even says). If you want that built next, happy to — it's
just worth deciding explicitly rather than bundling it into this pass.

## Not touched

The `frontend/` folder wasn't changed — the two new endpoints are there and
ready to wire into a UI (e.g. a small "Community Outreach" panel on the
recipient's request page, polling `/outreach` for status and offering the
CSV download once `status == "ready"`), if you'd like that built next.
