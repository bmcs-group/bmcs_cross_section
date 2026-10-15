# SCITE Deployment Scripts

Unified deployment scripts following the pattern used in `bmcs_apps`, `icc_apps`, and `cframe`.

## Scripts Overview

### `setup.sh`
Bootstrap or update the SCITE development environment.
- Creates `.venv` virtual environment if missing
- Installs/upgrades all dependencies from `pyproject.toml`
- Installs SCITE in editable mode

```bash
./scripts/setup.sh          # Normal setup
./scripts/setup.sh --dev    # Include notebook extras (jupyter, ipywidgets)
```

### `run.sh`
Pull-and-run entry point for local development.
- Runs `setup.sh` to ensure environment is current
- Starts Streamlit on configured port

```bash
./scripts/run.sh
```

**Environment variables** (all optional):
- `SCITE_PORT` — Streamlit port (default: 8503)
- `SCITE_HOST` — Bind address (default: localhost)
- `SCITE_BASE_URL` — Server base URL path (default: /)
- `SCITE_BROWSER` — Open browser on start (default: true)

**Examples:**
```bash
# Run on different port
SCITE_PORT=8888 ./scripts/run.sh

# Run on server without opening browser
SCITE_BROWSER=false SCITE_HOST=0.0.0.0 ./scripts/run.sh

# Run with base URL path (for reverse proxy)
SCITE_BASE_URL=/scite ./scripts/run.sh
```

### `restart.sh`
Fast restart without running setup.
- Kills any process on the configured port
- Relaunches Streamlit immediately

```bash
./scripts/restart.sh
```

Uses same environment variables as `run.sh`.

### `deploy.sh`
Production deployment script for `streamlit.imb.rwth-aachen.de`.

```bash
# On deployment server
cd /opt/scite-app
git pull origin gdt-2026
./scripts/deploy.sh
./scripts/run.sh
```

## Deployment Workflow

### Local Development
```bash
# Initial setup
./scripts/setup.sh

# Start development server
./scripts/run.sh

# After making changes (fast restart)
./scripts/restart.sh
```

### Production Deployment

**On local machine:**
```bash
git add -A
git commit -m "Your changes"
git push origin gdt-2026
```

**On deployment server:**
```bash
ssh streamlit@streamlit.imb.rwth-aachen.de
cd /opt/scite-app
git pull origin gdt-2026
./scripts/deploy.sh
./scripts/restart.sh  # or ./scripts/run.sh for full restart
```

## Port Allocations

To avoid conflicts with other CSCP apps:
- **BMCS** (`bmcs_apps`): Port 8501
- **ICC** (`icc_apps`): Port 8502
- **SCITE** (`scite`): Port 8503

## Requirements

- Python 3.10 or higher
- `lsof` command (for `restart.sh` to kill processes on port)

## Notes

- All scripts are **idempotent** — safe to run multiple times
- `.venv` is created in the repository root (ignored by git)
- Scripts automatically find the repo root regardless of where they're called from
