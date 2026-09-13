#!/usr/bin/env bash
# Plain-supervisor / tmux alternative to outreach-worker.service.
set -euo pipefail
cd "$(dirname "$0")"

python orchestrator.py \
  --mongo-uri "${MONGO_URI:-mongodb://localhost:27017}" \
  --mongo-db "${MONGO_DB:-blood_donor_platform}" \
  --osm-db "${OSM_DB:-../OsmProject/osmharvest.db}" \
  --export-dir "${OSM_EXPORT_DIR:-../OsmProject/exports}" \
  --contacts-dir "${CONTACTS_DIR:-./contacts}" \
  --max-places "${MAX_PLACES:-40}" \
  --poll "${POLL_SECONDS:-30}" \
  -v
