#!/usr/bin/env bash
# scripts/restart.sh — Kill the running SCITE Streamlit app and restart it.
# No setup/pip install — just a fast kill + relaunch.
#
# Environment variables (same as run.sh):
#   SCITE_PORT   (default: 8503)
#   SCITE_HOST   (default: localhost)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
STREAMLIT="$VENV/bin/streamlit"

PORT="${SCITE_PORT:-8503}"
HOST="${SCITE_HOST:-localhost}"
BASE_URL="${SCITE_BASE_URL:-/}"
OPEN_BROWSER="${SCITE_BROWSER:-true}"

# ── Kill any process already listening on the port ────────────────────────
PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [[ -n "$PIDS" ]]; then
    echo "Stopping process(es) on port $PORT: $PIDS"
    kill $PIDS
    # Give it a moment to release the port
    for i in 1 2 3 4 5; do
        lsof -ti :"$PORT" &>/dev/null || break
        sleep 0.4
    done
fi

# ── Restart ───────────────────────────────────────────────────────────────
echo "Starting SCITE App on http://${HOST}:${PORT}/"
echo "Press Ctrl+C to stop."
echo ""

STREAMLIT_ARGS=(
    "$REPO_ROOT/scite/streamlit_app/scite_app.py"
    --server.port "$PORT"
    --server.address "$HOST"
    --server.headless "$([ "$OPEN_BROWSER" = false ] && echo true || echo false)"
    --browser.gatherUsageStats false
)

if [[ "$BASE_URL" != "/" ]]; then
    STREAMLIT_ARGS+=(--server.baseUrlPath "$BASE_URL")
fi

exec "$STREAMLIT" run "${STREAMLIT_ARGS[@]}"
