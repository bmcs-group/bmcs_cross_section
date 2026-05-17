#!/usr/bin/env bash
# scripts/run_scite_app.sh — Launch the cframe-based SCITE course app.
#
# This runs the new scite_app (cframe-based course framework)
# instead of the original streamlit_app (view-pane based).
#
# Usage:
#   ./scripts/run_scite_app.sh
#
# Environment variables (all optional):
#   SCITE_PORT        Port to run on (default: 8504)
#   SCITE_HOST        Host to bind to (default: localhost)
#   SCITE_BASE_URL    Server base URL path (default: /)
#   SCITE_BROWSER     Open browser on start (default: true)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
STREAMLIT="$VENV/bin/streamlit"

# ── Environment variable defaults ─────────────────────────────────────────
PORT="${SCITE_PORT:-8504}"
HOST="${SCITE_HOST:-localhost}"
BASE_URL="${SCITE_BASE_URL:-/}"
BROWSER="${SCITE_BROWSER:-true}"

# ── Ensure environment is set up ──────────────────────────────────────────
"$REPO_ROOT/scripts/setup.sh"

# ── Launch Streamlit ───────────────────────────────────────────────────────
echo "Starting SCITE App (cframe) on http://$HOST:$PORT$BASE_URL"
exec "$STREAMLIT" run "$REPO_ROOT/scite/scite_app/app.py" \
    --server.port="$PORT" \
    --server.address="$HOST" \
    --server.baseUrlPath="$BASE_URL" \
    --server.headless=$([ "$BROWSER" = "false" ] && echo "true" || echo "false")
