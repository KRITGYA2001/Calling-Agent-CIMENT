#!/usr/bin/env bash
# On the VM: stop the backend, wipe demo data, reseed from scripts/seed_data.py, start the backend.
# Usage: bash scripts/demo_reset.sh           (everything: wipe + reseed)
#        bash scripts/demo_reset.sh --calls   (only wipe call history; keeps leads and DNC list)
# Run from ~/app on the VM (the folder that contains app/, scripts/ and venv/).
set -e
cd "$(dirname "$0")/.."
PY="$(pwd)/venv/bin/python"
[ -x "$PY" ] || PY="$(pwd)/.venv/bin/python"
sudo systemctl stop cimet-backend
trap 'sudo systemctl start cimet-backend' EXIT   # never leave the backend stopped, even on error
"$PY" scripts/clear_data.py "$@"
[ "$1" = "--calls" ] || "$PY" scripts/seed_data.py
echo "Backend restarting."
