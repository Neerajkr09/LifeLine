@echo off
REM Windows: keep the worker alive across crashes and network outages.
REM Progress lives in osmharvest.db, so a restart costs at most one request.
cd /d "%~dp0"
if "%OSMHARVEST_USER_AGENT%"=="" (
    set "OSMHARVEST_USER_AGENT=osm-harvester/1.0 (blood-donor-outreach-platform; contact: krneeraj.0509@gmail.com)"
)
:loop
python -m osmharvest run --follow --log-file logs\worker.log
echo [%date% %time%] worker exited with %errorlevel%; restarting in 60s >> logs\supervisor.log
timeout /t 60 /nobreak >nul
goto loop
