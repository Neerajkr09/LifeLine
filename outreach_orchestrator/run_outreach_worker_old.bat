@echo off
REM Windows: keep the orchestrator alive across crashes.
REM Progress lives in MongoDB (outreach.status) and osmharvest.db, so a
REM restart never re-scrapes a request that already reached "ready".
cd /d "%~dp0"

if "%MONGO_URI%"=="" set "MONGO_URI=mongodb://localhost:27017"
if "%MONGO_DB%"=="" set "MONGO_DB=blood_donor_platform"
if "%OSM_DB%"=="" set "OSM_DB=..\OsmProject\osmharvest.db"
if "%OSM_EXPORT_DIR%"=="" set "OSM_EXPORT_DIR=..\OsmProject\exports"
if "%CONTACTS_DIR%"=="" set "CONTACTS_DIR=.\contacts"
if "%MAX_PLACES%"=="" set "MAX_PLACES=40"
if "%POLL_SECONDS%"=="" set "POLL_SECONDS=30"

:loop
python orchestrator.py ^
    --mongo-uri "%MONGO_URI%" ^
    --mongo-db "%MONGO_DB%" ^
    --osm-db "%OSM_DB%" ^
    --export-dir "%OSM_EXPORT_DIR%" ^
    --contacts-dir "%CONTACTS_DIR%" ^
    --max-places %MAX_PLACES% ^
    --poll %POLL_SECONDS% ^
    -v
echo [%date% %time%] orchestrator exited with %errorlevel%; restarting in 30s
timeout /t 30 /nobreak >nul
goto loop
