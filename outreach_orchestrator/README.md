# outreach_orchestrator

The glue between the three projects. Watches MongoDB for blood requests
whose outreach is queued (`outreach.status == "osm_submitted"`, set the
moment a recipient submits a request -- see
`blood-donor-platform/backend/app/services/outreach_service.py`), waits for
the matching **osmharvest** job to finish, then runs **email_outreach**'s
scraping stage and writes the result back to Mongo.

It does **not** talk to Overpass itself -- that's `osmharvest run --follow`'s
job, running as its own process. This script only reacts once that worker
marks a job `COMPLETED` / `COMPLETED_WITH_ERRORS`.

```
recipient submits request
        |
        v
FastAPI backend: fast local sqlite insert into osmharvest.db, returns immediately
        |
        v
osmharvest worker (separate process, already running):
  fetches from Overpass, writes places_<id>.csv, marks job COMPLETED
        |
        v
outreach_orchestrator (this): notices COMPLETED, runs email_outreach
  on places_<id>.csv, writes contacts_<id>.csv, updates Mongo
        |
        v
recipient's app can now GET /blood-requests/{id}/outreach -> status "ready"
                          GET /blood-requests/{id}/outreach/contacts -> the CSV
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # also installs osmharvest + email_outreach, editable
```

`email_outreach` needs a real Chrome/Chromium on this machine -- see its own
README.

## Run

```bash
python orchestrator.py \
  --mongo-uri mongodb://localhost:27017 \
  --mongo-db blood_donor_platform \
  --osm-db ../OsmProject/osmharvest.db \
  --export-dir ../OsmProject/exports \
  --contacts-dir ./contacts \
  --max-places 40 \
  --poll 30
```

Or `./run_outreach_worker.sh` (reads the same options from environment
variables), or install `outreach-worker.service` alongside
`osmharvest.service` for a VPS deployment. `--once` runs a single sweep and
exits, useful for testing or driving it from cron instead of a long-lived
process.

## Tuning

- `--max-places` bounds how many of the *nearest* places (per request) get a
  website visit, so one large-radius request can't monopolize the scraper
  for hours. Raise it for deeper coverage if you have the time budget.
- `--poll` is how often it checks osmharvest.db for newly-completed jobs. 30s
  is fine for most cases -- an OSM harvest job usually takes minutes, not
  seconds, so there's no benefit to polling faster.

## Failure handling

Every request is processed independently and wrapped in its own try/except:
one bad website, a locked database, a missing job -- none of it stops the
sweep for every other pending request, and none of it takes the service
down. A request that fails is marked `outreach.status = "failed"` with the
error message attached, not silently dropped or retried forever.
