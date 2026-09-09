#!/usr/bin/env bash
# dse-data installer — creates the venv, installs all dependencies, smoke-tests.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> dse-data setup"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.9+ first." >&2
  exit 1
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "ERROR: dse-data requires Python 3.9+ (found $($PYTHON --version 2>&1))." >&2
  exit 1
fi

# 1 · venv
if [ ! -x .venv/bin/python ]; then
  echo "==> creating .venv"
  "$PYTHON" -m venv .venv || {
    echo "ERROR: venv creation failed. On Debian/Ubuntu: sudo apt install python3-venv python3-full" >&2
    exit 1
  }
fi

# Some distros (Ubuntu without python3-venv) create a venv that exits 0 but has
# neither pip nor ensurepip — detect and bootstrap before the dependency step.
if ! ./.venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "==> venv has no pip — bootstrapping"
  if ! ./.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1; then
    echo "==> ensurepip unavailable — falling back to get-pip.py"
    GETPIP="$(mktemp -d)/get-pip.py"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$GETPIP" \
      && ./.venv/bin/python "$GETPIP" >/dev/null 2>&1 \
      || { echo "ERROR: could not bootstrap pip into the venv. On Debian/Ubuntu: sudo apt install python3-venv python3-full, then rerun ./setup.sh" >&2; exit 1; }
  fi
fi

# 2 · dependencies (prefer the pinned lockfile for reproducible installs)
echo "==> installing dependencies (pinned)"
./.venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade pip
REQ=requirements-lock.txt; [ -f "$REQ" ] || REQ=requirements.txt
./.venv/bin/pip install --quiet --disable-pip-version-check -r "$REQ"
# tvdatafeed-enhanced imports `websocket` but doesn't declare it — keep explicit:
./.venv/bin/python -c "import websocket" 2>/dev/null || \
  ./.venv/bin/pip install --quiet --disable-pip-version-check websocket-client

# 3 · smoke test (needs internet; works any day, market hours not required)
echo "==> smoke test: DSEX index via TradingView"
if ./.venv/bin/python dse.py index >/tmp/dse_smoke.json 2>/tmp/dse_smoke.err; then
  echo "✓ dse-data is ready."
  echo "  try:  ./.venv/bin/python dse.py snapshot --top 5"
  echo "        ./.venv/bin/python dse.py chart SQURPHARMA --bars 30"
else
  echo "⚠ install finished but the smoke test failed — check /tmp/dse_smoke.err"
  echo "  (no internet? blocked TradingView? retry later with: ./.venv/bin/python dse.py index)"
fi
