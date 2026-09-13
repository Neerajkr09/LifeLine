# email_outreach

Stage 2 of the outreach pipeline. Takes a `places_<request_id>.csv` file
written by **OsmProject** (stage 1) and produces a `contacts_<request_id>.csv`
of usable contact emails: OSM-tag emails used as-is, plus emails scraped from
a place's own website (contact/enquiry page) when OSM didn't already have one.

This is a straight refactor of the two scripts you'd already written
(`Scraper.py` and the CSV processor) into an importable package, so it can be
called directly by `outreach_orchestrator` instead of run as a one-off script
against a manually-prepared `input.csv`.

## Install

Requires a real Chrome/Chromium browser and a matching chromedriver on the
machine that runs this (Selenium Manager will usually fetch a matching driver
automatically the first time you run it, as long as Chrome itself is
installed).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or: pip install -r requirements.txt
```

On a Debian/Ubuntu server:

```bash
sudo apt-get update && sudo apt-get install -y chromium chromium-driver
```

## Standalone usage

```bash
python -m email_outreach.pipeline \
  --request-id 87654321 \
  --places-csv ../OsmProject/exports/87654321/places_87654321.csv \
  --output-dir contacts \
  --max-places 40
```

Writes `contacts/contacts_87654321.csv` with columns:

| column | meaning |
|---|---|
| `request_id` | the osmharvest request id this row belongs to |
| `category` | `college` / `university` / `restaurant` / `pub` / ... |
| `name` | place name |
| `distance_metres` | distance from the search origin |
| `website` | the place's website, if any |
| `source` | `osm_tag` (free, from OSM's own data) or `scraped_website` |
| `extracted_email` | one email per row (a place with 2 emails -> 2 rows) |

Re-running the same command resumes: rows already written are not
reprocessed (progress is checkpointed to `contacts_87654321.progress.json`).

## Why `max_places` exists

Each site visit can take up to ~20 seconds (page load timeout) and OSM
searches over a large radius can return hundreds of places. `max_places`
caps how many of the *nearest* places (the input CSV is already
distance-sorted) are considered at all, so a single job has a bounded,
predictable runtime. Raise it if you want deeper coverage and can afford the
extra time; there's no hard need to lower it below the default the
orchestrator uses unless sites in your area are unusually slow to time out.

## What this does *not* do

This package only **collects** contact emails into a CSV. It does not send
any email to them. Sending unsolicited outreach at scale to addresses
harvested this way has its own legal and ethical considerations (anti-spam
law, opt-out handling, rate limits per recipient domain, etc.) that are
deliberately out of scope here -- treat the output CSV as a lead list for a
human to review and reach out from, not as an autosend queue.
