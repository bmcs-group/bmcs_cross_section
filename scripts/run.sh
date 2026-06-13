#!/usr/bin/env bash
# scripts/run.sh — Pull-and-run entry point for SCITE Streamlit App.
#
# After every `git pull` just run this script — it will:
#   1. Re-run setup.sh (idempotent: only installs new/changed packages)
#   2. Start Streamlit on the configured port
#
# Environment variables (all optional):
#   SCITE_PORT        Streamlit port          (default: 8503)
#   SCITE_HOST        Bind address            (default: localhost)
#   SCITE_BASE_URL    --server.baseUrlPath    (default: /)
#   SCITE_BROWSER     Open browser on start   (default: true; set false on servers)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
STREAMLIT="$VENV/bin/streamlit"

PORT="${SCITE_PORT:-8503}"
HOST="${SCITE_HOST:-localhost}"
BASE_URL="${SCITE_BASE_URL:-/}"
OPEN_BROWSER="${SCITE_BROWSER:-true}"

# ── 1. Ensure environment is up to date ───────────────────────────────────
"$REPO_ROOT/scripts/setup.sh"

# ── 2. Launch Streamlit ────────────────────────────────────────────────────
echo ""
echo "Starting SCITE App on http://${HOST}:${PORT}${BASE_URL}"
echo "Press Ctrl+C to stop."
echo ""

STREAMLIT_ARGS=(
    "$REPO_ROOT/scite/streamlit_app/scite_app.py"
    --server.port "$PORT"
    --server.address "$HOST"
    --server.headless "$([ "$OPEN_BROWSER" = false ] && echo true || echo false)"
    --browser.gatherUsageStats false
)

# Only pass baseUrlPath when it is not the root — passing "/" breaks routing
# in Streamlit 1.36+ and causes an empty page to be served.
if [[ "$BASE_URL" != "/" ]]; then
    STREAMLIT_ARGS+=(--server.baseUrlPath "$BASE_URL")
fi

exec "$STREAMLIT" run "${STREAMLIT_ARGS[@]}"
