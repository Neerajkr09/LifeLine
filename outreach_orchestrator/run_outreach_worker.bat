@echo off
REM Windows: keep the orchestrator alive across crashes.
REM Progress lives in MongoDB (outreach.status) and osmharvest.db, so a
REM restart never re-scrapes a request that already reached "ready".
REM
REM No env vars are set here on purpose -- orchestrator.py resolves each
REM setting itself, in this order: CLI flag > already-set shell env var >
REM .env file next to orchestrator.py > built-in default. Fill in .env once
REM (copy .env.example to .env) and this script needs nothing else.
cd /d "%~dp0"

:loop
python orchestrator.py -v
echo [%date% %time%] orchestrator exited with %errorlevel%; restarting in 30s
timeout /t 30 /nobreak >nul
goto loop
