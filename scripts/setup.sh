#!/usr/bin/env bash
# scripts/setup.sh — Bootstrap or update the SCITE App environment.
#
# Safe to run at any time:
#   • Creates .venv if it doesn't exist
#   • Installs / upgrades all packages declared in pyproject.toml
#   • Editable-installs scite itself so imports resolve
#
# Usage:
#   ./scripts/setup.sh          # normal setup
#   ./scripts/setup.sh --dev    # also install dev extras (notebook, ipykernel etc.)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
EXTRAS=""
[[ "${1:-}" == "--dev" ]] && EXTRAS="[notebook]"

# ── 1. Require Python 3.10+ ────────────────────────────────────────────────
PYTHON=$(command -v python3.13 2>/dev/null || command -v python3.12 2>/dev/null || \
         command -v python3.11 2>/dev/null || command -v python3.10 2>/dev/null || \
         command -v python3    2>/dev/null || true)
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python 3.10+ not found on PATH." >&2; exit 1
fi
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 10) )); then
    echo "ERROR: Python 3.10+ required, found $PY_VERSION." >&2; exit 1
fi
echo "Using Python $PY_VERSION ($PYTHON)"

# ── 2. Create venv if absent ───────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
    echo "Creating virtual environment at .venv ..."
    "$PYTHON" -m venv "$VENV"
fi

PIP="$VENV/bin/pip"

# ── 3. Upgrade pip silently ────────────────────────────────────────────────
"$PIP" install --quiet --upgrade pip

# ── 4. Install / sync all deps from pyproject.toml ────────────────────────
# --upgrade ensures newly added packages are fetched on subsequent runs.
echo "Installing dependencies (editable) ..."
"$PIP" install --upgrade -e "${REPO_ROOT}${EXTRAS}"

# ── 5. Install cframe from local repo (if available) ──────────────────────
CFRAME_PATH="$HOME/Coding/cframe"
if [[ -d "$CFRAME_PATH" ]]; then
    echo "Installing cframe from local repo ($CFRAME_PATH) ..."
    "$PIP" install -e "$CFRAME_PATH[streamlit]"
else
    echo "WARNING: cframe not found at $CFRAME_PATH — cframe-based apps will not work." >&2
fi

echo ""
echo "Setup complete. To start the app run:  ./scripts/run.sh"
