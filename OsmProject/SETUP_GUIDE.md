# Setup and Testing Guide (Windows, beginner-friendly)

> This guide walks through **OsmProject on its own**, from scratch. If
> you're setting up the full merged pipeline (blood-donor-platform +
> OsmProject + email_outreach + outreach_orchestrator together), use
> `WINDOWS_SETUP.md` at the root of the merged project instead — it covers
> all four pieces in the right order. This file is still accurate for
> understanding or testing OsmProject in isolation.

Follow these in order. Copy each command exactly, press Enter, read what it
prints before moving to the next one.

---

## Step 0 — Check your Python

Open **Command Prompt** (press Windows key, type `cmd`, press Enter) and run:

```
python --version
```

You need **3.10 or higher**. You have 3.11, which is fine.

---

## Step 1 — Create the folder structure

This is the part that trips people up, so read it slowly.

You are **not** pasting all the code into one folder as loose files. There is
one outer folder, and inside it a **sub-folder called `osmharvest`** that holds
most of the Python files. The sub-folder name matters — `python -m osmharvest`
looks for a folder with exactly that name.

Run these commands one at a time:

```
cd C:\Users\Naman Srivastava\Documents
mkdir OsmProject
cd OsmProject
mkdir osmharvest
mkdir logs
```

You should now have this, and this is what it must look like when you are done
pasting files:

```
C:\Users\Naman Srivastava\Documents\OsmProject\
│
├── osmharvest\              <-- sub-folder, 10 files inside
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── exporters.py
│   ├── geo.py
│   ├── overpass.py
│   ├── parsing.py
│   ├── store.py
│   └── worker.py
│
├── logs\                    <-- empty for now
├── test_harvest.py          <-- outside the sub-folder
└── requirements.txt         <-- outside the sub-folder
```

Note the two files that live **outside** `osmharvest\`: `test_harvest.py` and
`requirements.txt`. Putting those inside the sub-folder will break things.

---

## Step 2 — Create the files

Open **Notepad** (or VS Code, or Notepad++ — anything that saves plain text).

For each of the 12 files: paste the contents, then **Save As**.

### Saving correctly in Notepad — important

Notepad likes to add `.txt` to the end of filenames, which silently breaks
everything. To prevent it:

1. File → Save As
2. Navigate to the right folder
3. In the **"Save as type"** dropdown, choose **"All Files (\*.\*)"**
4. Type the full filename including `.py`, e.g. `worker.py`
5. Set **Encoding** to **UTF-8**
6. Save

### The two smallest files

`osmharvest\__init__.py` — three lines:

```python
"""Resumable OpenStreetMap POI harvester."""
__version__ = "1.0.0"
```

`osmharvest\__main__.py` — three lines:

```python
import sys
from .cli import main
sys.exit(main())
```

`requirements.txt` — one line (this one is **not** a .py file):

```
requests>=2.31.0
```

The other 9 files are the ones I gave you. Paste each into the matching
filename.

### Verify the structure

```
cd C:\Users\Naman Srivastava\Documents\OsmProject
dir
dir osmharvest
```

You must see exactly 10 `.py` files inside `osmharvest`. If you see
`worker.py.txt`, redo Step 2 with "All Files" selected.

---

## Step 3 — Install the one dependency

```
pip install -r requirements.txt
```

You already have `requests` 2.31.0, so this will likely say "already
satisfied". That is the only third-party package this uses — everything else
(SQLite, CSV, JSON) ships with Python.

---

## Step 4 — Set your contact address

**This step is now optional** — `osmharvest\config.py` already defaults
`OSMHARVEST_USER_AGENT` to `namansrivastava001.jnp@gmail.com`, so a plain
`python -m osmharvest doctor` or `run` already sends a real, correct
contact address with zero setup. Only do this if you want to use a
*different* address for a specific run:

```
set OSMHARVEST_USER_AGENT=osm-harvester/1.0 (student project; namansrivastava001.jnp@gmail.com)
```

Put a real email you check. This tells the OpenStreetMap volunteers who is
making the requests. Anonymous clients get blocked first when a server operator
is dealing with load.

**This resets every time you close Command Prompt.** Re-run it each session, or
skip ahead to Step 9 to make it permanent.

---

## Step 5 — Run the offline tests first

```
python test_harvest.py
```

This talks to **nothing** — it builds a fake city of 1,383 places and a fake
Overpass server that deliberately fails, then checks the code handles it. It
takes a few seconds.

You want to see this at the bottom:

```
ALL TESTS PASSED
```

If you see `ModuleNotFoundError: No module named 'osmharvest'`, you are in the
wrong folder or the sub-folder is misnamed. Go back to Step 1.

If you see `SyntaxError`, a file did not paste completely. Re-paste it.

**Why this matters:** if this passes, the logic is proven correct before you
send a single request to a real server. Debugging against a flaky public API is
miserable; debugging against a fake one that fails on command is easy.

---

## Step 6 — Check the real servers are reachable

```
python -m osmharvest doctor
```

Expected output looks roughly like:

```
User-Agent: osm-harvester/1.0 (student project; namansrivastava001.jnp@gmail.com)
  OK   overpass.kumi.systems
         Rate limit: 2
         2 slots available now.
  OK   overpass-api.de
  OK   overpass.osm.jp
  Sending a tiny live query...
  OK   query returned 3 element(s), data as of 2026-08-18T...
```

Some endpoints failing is normal and fine — the code rotates between them. You
only need **one** to say OK.

If **all three** fail, check your internet, then check whether a corporate or
university firewall is blocking them.

---

## Step 7 — Your first real job: Sandbach

Sandbach town centre is at **53.1439, -2.3661**.

```
python -m osmharvest submit --lat 53.1439 --lng -2.3661 --radius 5000
```

It prints something like:

```
Request ID: 47820193
  53.1439, -2.3661 within 5000m
  4 categorie(s): college, university, restaurant, pub
```

**Write that 8-digit number down.** Then run it (use your own number):

```
python -m osmharvest run --request-id 47820193
```

### What you will actually see

```
21:14:02 INFO    -> 47820193/college/DISCOVERY (attempt 1)
21:14:04 INFO       found 2 element(s) -> 1 detail batch(es)
21:14:07 INFO    -> 47820193/college/DETAIL#0 (attempt 1)
21:14:09 INFO       stored 2 place(s), 2 new to this request, 0 outside radius
21:14:12 INFO    -> 47820193/university/DISCOVERY (attempt 1)
...
Tasks done 9 | deferred 0 | dead 0
Places linked 74 | outside radius 31
Overpass requests 9
```

### Set your expectations honestly

**Sandbach will finish in about a minute, not two days.** It is a market town
of roughly 18,000 people. A 5 km circle around it holds perhaps 40–90 pubs and
restaurants, a couple of colleges, and probably zero universities. That is the
correct answer, not a failure.

You do **not** need to leave your laptop running for this. The two-day
architecture matters when you scale to hundreds of coordinates or a whole
county — not for one small town.

Also: expect **very few emails**. OSM email coverage runs about 3–10%. From
Sandbach you might get 2–8 addresses. Websites will do better, maybe 40–50%.
That is a limit of what volunteers have mapped, not a bug in the code.

---

## Step 8 — Look at your results

```
python -m osmharvest status --request-id 47820193
```

```
Request 47820193 - COMPLETED
  53.1439, -2.3661 within 5000m | college, university, restaurant, pub

  Progress by category
    college      [####################] 100.0%  2/2
    pub          [####################] 100.0%  2/2
    restaurant   [####################] 100.0%  2/2
    university   [####################] 100.0%  1/1

  Places 74 | with email 5 | with website 33 | with phone 21
```

Your files are in:

```
C:\Users\Naman Srivastava\Documents\OsmProject\exports\47820193\
```

Open `places_47820193.csv` in Excel to browse everything, and
`emails_47820193.csv` for just the contacts. Drag
`places_47820193.geojson` onto **geojson.io** in your browser to see them on a
map — that is the fastest way to confirm the radius looks right.

---

## Step 9 — Prove to yourself that it resumes

This is the feature you are relying on for the long runs, so test it now while
the job is small.

Submit a bigger job — Manchester, which has far more data:

```
python -m osmharvest submit --lat 53.4808 --lng -2.2426 --radius 5000
python -m osmharvest run --request-id <the new id>
```

While it is running, **press Ctrl+C once**. It will say:

```
Shutdown requested - finishing current task first
```

Then run the exact same `run` command again. Watch it skip everything already
done and continue from where it stopped. Check with `status` that the count
went up rather than restarting from zero.

That is the whole safety net. Once you have seen it work, you can trust a
multi-day run.

---

## Step 10 — Make the settings permanent (optional)

So you do not retype Step 4 every session:

```
setx OSMHARVEST_USER_AGENT "osm-harvester/1.0 (student project; namansrivastava001.jnp@gmail.com)"
```

`setx` writes it permanently, but **only affects new Command Prompt windows** —
close and reopen after running it.

To slow the requests down further (kinder to the servers, and worth doing on a
long run):

```
setx OSMHARVEST_MIN_INTERVAL 5.0
```

---

## Step 11 — Running many coordinates

This is where the multi-day design earns its keep. Submit as many jobs as you
like, then run one worker over all of them:

```
python -m osmharvest submit --lat 53.1439 --lng -2.3661
python -m osmharvest submit --lat 53.4808 --lng -2.2426
python -m osmharvest submit --lat 53.4084 --lng -2.9916
python -m osmharvest submit --lat 51.5074 --lng -0.1278

python -m osmharvest run --follow --log-file logs\worker.log
```

`--follow` keeps the worker alive: it drains the queue, then polls for new
work every 30 seconds. Leave that window open for as long as you want. Each
request id gets its own folder under `exports\`.

To watch progress from a **second** Command Prompt window while the first is
still running:

```
cd C:\Users\Naman Srivastava\Documents\OsmProject
python -m osmharvest status
```

Reading while writing is safe — export files are written to a temp file and
renamed, so you never open a half-written CSV.

### Keeping a laptop awake for a long run

Windows will sleep and stop your worker. Before a long run:

Settings → System → Power & battery → Screen and sleep → set **"When plugged
in, put my device to sleep after"** to **Never**.

Closing the lid may still sleep it — check Control Panel → Power Options →
"Choose what closing the lid does" → set to **Do nothing** when plugged in.

---

## Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| `No module named 'osmharvest'` | Wrong folder, or sub-folder misnamed | `cd` to `OsmProject`; check `dir osmharvest` shows 10 files |
| `SyntaxError` | A file pasted incompletely | Re-paste that file |
| `unrecognized arguments` | Typo in a flag | Run `python -m osmharvest run --help` |
| `HTTP 406` | Wrong POST encoding | Should not happen now; if it does, a file did not paste fully |
| `HTTP 504` in the log | Server busy — **normal** | Nothing. It retries and rotates automatically |
| `HTTP 429` in the log | You are going too fast | `setx OSMHARVEST_MIN_INTERVAL 10.0`, reopen cmd |
| Job says `COMPLETED_WITH_ERRORS` | Some batches gave up | `python -m osmharvest retry --request-id <id>` then `run` again |
| `0 places` | Genuinely nothing there, or swapped lat/lng | UK longitude is **negative**: `-2.3661`, not `2.3661` |
| Excel mangles special characters | Encoding | Files are UTF-8 with BOM; Excel should handle it. If not, use Import Data |

**The single most common mistake:** swapping latitude and longitude. Sandbach
is `--lat 53.1439 --lng -2.3661`. If you get zero results in the UK, check the
minus sign is on the longitude.

---

## Quick command reference

```
python -m osmharvest doctor
python -m osmharvest submit --lat 53.1439 --lng -2.3661 --radius 5000
python -m osmharvest submit --lat 53.1439 --lng -2.3661 --categories pub restaurant
python -m osmharvest run --request-id 47820193
python -m osmharvest run --follow --log-file logs\worker.log
python -m osmharvest status
python -m osmharvest status --request-id 47820193
python -m osmharvest export --request-id 47820193
python -m osmharvest retry --request-id 47820193
```

Categories available: `college university restaurant pub bar cafe fast_food school`

---

## Before you buy the VPS

Everything transfers by copying the folder. `osmharvest.db` is the entire job
state — copy that one file and a worker on the VPS picks up exactly where your
laptop left off.

But read the last section of the README first. If you are going to run for
days across many coordinates, running **your own Overpass server** in Docker on
that VPS removes the 504s, the rate limits and the waiting entirely. Same code,
one changed flag: `--endpoints http://localhost:12345/api/interpreter`.
