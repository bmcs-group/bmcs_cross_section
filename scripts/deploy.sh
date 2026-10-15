#!/usr/bin/env bash
# scripts/deploy.sh — Install/update scite and dependencies (for production deployment).
#
# USAGE on deployment server (streamlit.imb.rwth-aachen.de):
#   1. SSH to server: ssh streamlit@streamlit.imb.rwth-aachen.de
#   2. Navigate to: cd /opt/scite-app
#   3. Pull changes: git pull origin gdt-2026
#   4. Run deploy: bash scripts/deploy.sh
#
# This script:
#   - Creates/updates .venv
#   - Installs all dependencies from pyproject.toml
#   - Installs scite in editable mode
#
# For private CSCP dependencies (if needed):
#   Create a .env file in repo root with deploy tokens:
#     DEPLOY_TOKEN_CFRAME=<token-name>:<token-secret>
#     DEPLOY_TOKEN_IBVPY=<token-name>:<token-secret>
#   (Deploy tokens: GitLab → Settings → Repository → Deploy tokens)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
GITLAB="git.rwth-aachen.de/cscp"

echo "==> SCITE Deployment Script"
echo ""

# ── 1. Setup virtual environment ──────────────────────────────────────────
echo "==> Running setup.sh to ensure environment is ready..."
"$REPO_ROOT/scripts/setup.sh"

# ── 2. Optional: Install private CSCP dependencies ───────────────────────
# Uncomment and configure if SCITE needs cframe, ibvpy, etc.
#
# if [[ -f "$REPO_ROOT/.env" ]]; then
#     echo "==> Loading deploy tokens from .env..."
#     set -a && source "$REPO_ROOT/.env" && set +a
#     
#     PIP="$VENV/bin/pip"
#     
#     if [[ -n "${DEPLOY_TOKEN_CFRAME:-}" ]]; then
#         echo "==> Installing cframe..."
#         "$PIP" install -e "git+https://${DEPLOY_TOKEN_CFRAME}@${GITLAB}/cframe.git#egg=cframe"
#     fi
#     
#     if [[ -n "${DEPLOY_TOKEN_IBVPY:-}" ]]; then
#         echo "==> Installing cscp_ibvpy..."
#         "$PIP" install -e "git+https://${DEPLOY_TOKEN_IBVPY}@${GITLAB}/cscp_ibvpy.git#egg=cscp_ibvpy"
#     fi
# fi

echo ""
echo "==> Deploy complete!"
echo ""
echo "To start the app:"
echo "  ./scripts/run.sh"
echo ""
echo "To restart quickly (without reinstalling):"
echo "  ./scripts/restart.sh"
