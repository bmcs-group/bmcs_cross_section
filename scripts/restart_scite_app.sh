#!/usr/bin/env bash
# restart_scite_app.sh — Kill and restart SCITE app (port 8504)

set -e

echo "Stopping SCITE app..."
pkill -f "streamlit run.*scite_app/app.py" || true
sleep 1

echo "Starting SCITE app..."
cd "$(dirname "$0")/.."
SCITE_BROWSER=false SCITE_PORT=8504 ./scripts/run_scite_app.sh
