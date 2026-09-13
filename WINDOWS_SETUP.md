# Windows Setup (VS Code)

Commands below are shown for **both PowerShell and Command Prompt (cmd)** —
use whichever your VS Code terminal actually is. Check the terminal panel's
dropdown (top-right of the terminal tab): it says "powershell" or "cmd" (or
"Command Prompt"). If you're not sure, type `$PSVersionTable` and press
Enter — if that prints a table, you're in PowerShell; if it errors, you're
in cmd.

Four things run at once, each in its own VS Code terminal tab:
**1) OsmProject worker, 2) outreach_orchestrator, 3) the FastAPI backend,
4) the frontend (optional).** Leave all of them running while you use the app.

## 0. Prerequisites

- **Python 3.10+** — https://python.org/downloads, tick "Add python.exe to PATH" during install.
- **Google Chrome** — needed for the email scraper. If it's already installed, nothing else to do: Selenium (already pinned in `requirements.txt`) auto-downloads a matching chromedriver the first time it runs. No manual chromedriver install on Windows.
- **MongoDB** — pick one:
  - **Atlas (easiest, no install)**: free cluster at https://www.mongodb.com/cloud/atlas → Database → Connect → Drivers → copy the connection string (looks like `mongodb+srv://user:pass@cluster.mongodb.net/...`). Under Network Access, add your current IP (or `0.0.0.0/0` for local dev only).
  - **Local install**: https://www.mongodb.com/try/download/community, install as a Windows service — it'll be running at `mongodb://localhost:27017` automatically, nothing to start by hand.
- **Node.js 18+** — only if you want the frontend running too: https://nodejs.org.
- **VS Code** with the Python extension (Extensions panel → search "Python" → install, by Microsoft).

## 1. Unpack and open the project

1. Extract `blood-donor-outreach-platform.zip` somewhere like `C:\Projects\`.
2. VS Code → File → Open Folder → select `C:\Projects\blood-donor-outreach-platform`.
3. Terminal menu → New Terminal. You'll open **three or four** of these tabs (one per service) as you go — use the `+` icon in the terminal panel, or the dropdown next to it, to add more.

## 2. One-time fix — PowerShell only, skip if you're in cmd

Activating a venv in PowerShell runs a `.ps1` script, which Windows blocks by
default. **cmd doesn't have this restriction at all — if your terminal says
"cmd", skip straight to step 3.** Otherwise, run this once (affects only
your user, only PowerShell scripts):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Type `Y` if it asks for confirmation. You won't need to do this again.

## 3. Terminal 1 — OsmProject worker



**cmd:**
```bat
cd blood-donor-outreach-platform\OsmProject
python -m venv .venv
or 
"C:\Users\krnee\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

Sanity-check Overpass connectivity before a real run (same command, either shell):

```
python -m osmharvest doctor
```

You should see `OK` next to each endpoint and your real email in the
`User-Agent:` line printed at the top (it's baked in by default — nothing
to set). Then start the worker and **leave this terminal running** (same in
both shells — `run_worker.bat` is a batch file, it runs the same way
regardless of which shell launches it):

```
run_worker.bat
```

(This restarts the worker automatically if it ever crashes — logs go to
`logs\worker.log`. To run it in the foreground without the auto-restart
wrapper instead: `python -m osmharvest run --follow --log-file logs\worker.log`.)

## 4. Terminal 2 — outreach_orchestrator

Open a **new** terminal tab (`+` icon), then:


**cmd:**
```bat
cd blood-donor-outreach-platform\outreach_orchestrator
python -m venv .venv
or
"C:\Users\krnee\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

Set your Mongo connection for this terminal session (skip this if you're
using local Mongo at the default `mongodb://localhost:27017` — that's
already the fallback):

**PowerShell:**
```powershell
$env:MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"
$env:MONGO_DB  = "blood_donor_platform"
```

**cmd** — ⚠️ use `set "NAME=value"` (quote wrapping the *whole*
`NAME=value`), not `set NAME="value"`. Atlas connection strings almost
always contain `&` (e.g. `...&w=majority`), and in cmd a bare `&` outside
quotes is a command separator — it'll silently cut your connection string in
half. The quoting below avoids that:
```bat
set "MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"
set "MONGO_DB=blood_donor_platform"
```

Do one test sweep first, so you see any errors immediately instead of
waiting on a 30-second poll loop:

**PowerShell:**
```powershell
python orchestrator.py --mongo-uri $env:MONGO_URI --mongo-db $env:MONGO_DB --osm-db ..\OsmProject\osmharvest.db --export-dir ..\OsmProject\exports --contacts-dir .\contacts --max-places 40 --once -v
```

**cmd:**
```bat
python orchestrator.py --mongo-uri "%MONGO_URI%" --mongo-db "%MONGO_DB%" --osm-db ..\OsmProject\osmharvest.db --export-dir ..\OsmProject\exports --contacts-dir .\contacts --max-places 40 --once -v
```

If that runs without errors (it'll just say "Sweep complete: 0 request(s)
advanced" if there's nothing pending yet — that's fine), start it for real
and **leave this terminal running** too (same command, either shell —
`run_outreach_worker.bat` already reads the `MONGO_URI`/`MONGO_DB` you just
set, quoted internally, so the `&` problem doesn't apply here):

```
run_outreach_worker.bat
```

## 5. Terminal 3 — Backend (FastAPI)

New terminal tab.



**cmd:**
```bat
cd blood-donor-outreach-platform\blood-donor-platform\backend
python -m venv .venv
or
"C:\Users\krnee\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
code .env
```

That last command opens `.env` in VS Code. Fill in:
- `MONGO_URI` — same connection string as Terminal 2 (paste it as plain
  text into the `.env` file directly — `.env` files aren't shell commands,
  so the cmd `&`-quoting issue above doesn't apply here, just paste it as-is)
- `JWT_SECRET_KEY` — replace with a real random value:
  ```
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
  paste the output in as `JWT_SECRET_KEY`.
- Leave `OSM_DB_PATH`, `OUTREACH_RADIUS_METRES`, `OUTREACH_CATEGORIES` as-is
  (they already point at the sibling `OsmProject` folder and default to 5km /
  college+university+restaurant+pub, matching what you asked for).

Save the file, then start the API and **leave this terminal running** (same
command, either shell):

```
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/api/docs in a browser — you should see the full
Swagger UI, including `POST /api/v1/blood-requests` and the two new
`.../outreach` endpoints. If that page loads, the backend, its imports of
`osmharvest`/`email_outreach`, and Mongo are all wired correctly.

## 6. Terminal 4 (optional) — Frontend

New terminal tab (identical in both shells):

```
cd blood-donor-outreach-platform\blood-donor-platform\frontend
npm install
npm run dev
```

Opens at http://localhost:5173 (already whitelisted in the backend's
`CORS_ORIGINS`, nothing to change).

## 7. Try the whole pipeline end to end

1. Register as a recipient in the app (or via `/api/docs`), log in.
2. Submit a blood request with a real lat/lng near you and upload any test
   PDF/image as the hospital document.
3. Watch **Terminal 1** — you'll see Overpass discovery/detail requests
   logging as the OSM job runs (takes anywhere from under a minute to a few
   minutes for a 5km radius).
4. Watch **Terminal 2** — once Terminal 1's job status flips to `COMPLETED`,
   you'll see `starting contact scrape`, then a Chrome window will briefly
   flash open/closed per site being visited, then `outreach ready, N
   contact(s)`.
5. Check progress any time:
   `GET http://127.0.0.1:8000/api/v1/blood-requests/{id}/outreach`
   (through `/api/docs`, with your bearer token).
6. Once `status: "ready"`, download the CSV:
   `GET .../outreach/contacts`

## 8. Stopping and restarting later

`Ctrl+C` in each terminal stops that service. Nothing is lost — osmharvest's
progress lives in `OsmProject\osmharvest.db`, the orchestrator's progress
lives in Mongo (`outreach.status`) plus per-request `.progress.json` files
in `outreach_orchestrator\contacts\`. Next time, just re-activate each venv
and re-run the same start command from steps 3–6 (skip the `pip install`
lines — only needed once, unless `requirements.txt` changes).

## Troubleshooting

| Problem | Fix |
|---|---|
| PowerShell: `cannot be loaded because running scripts is disabled` | Run the `Set-ExecutionPolicy` command from step 2 |
| cmd: `'python' is not recognized...` or `'.venv\Scripts\activate.bat' is not recognized` | Python isn't on PATH, or you're not in the folder you think — run `cd` with no arguments to check where you are, and `where python` to confirm Python is found |
| cmd: your Mongo connection stops working / orchestrator can't parse `--mongo-uri` | You set `MONGO_URI` without the `set "NAME=value"` quoting shown in step 4 — an unquoted `&` in the Atlas URI got treated as a command separator. Re-set it with the quoted form |
| `ModuleNotFoundError: No module named 'osmharvest'` in the backend or orchestrator | You're in the wrong venv, or `pip install -r requirements.txt` didn't finish — re-run it in that terminal |
| Backend starts but `/outreach` submission silently does nothing | Check `OSM_DB_PATH` in `.env` resolves correctly from `blood-donor-platform\backend\` — default `../../OsmProject/osmharvest.db` assumes the four project folders are still siblings, as unzipped |
| Chrome flashes open then the scrape fails every time | Update Chrome to the latest version — Selenium Manager needs a reasonably recent Chrome to match a chromedriver against |
| Orchestrator says `Sweep failed` with a Mongo auth/connection error | Double check the Mongo URI in that terminal (Atlas IP allowlist is a common culprit) |
