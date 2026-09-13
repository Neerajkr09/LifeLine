#!/usr/bin/env bash
# Keep the worker alive across crashes, reboots and network outages.
# Progress lives in SQLite, so an unexpected restart costs at most one request.
set -u
cd "$(dirname "$0")"
export OSMHARVEST_USER_AGENT="${OSMHARVEST_USER_AGENT:-osm-harvester/1.0 (blood-donor-outreach-platform; contact: krneeraj.0509@gmail.com)}"
while true; do
    python3 -m osmharvest run --follow --log-file logs/worker.log
    echo "[$(date -Is)] worker exited with $?; restarting in 60s" >> logs/supervisor.log
    sleep 60
done
