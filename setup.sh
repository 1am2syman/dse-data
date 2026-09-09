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

# 1 · venv
if [ ! -x .venv/bin/python ]; then
  echo "==> creating .venv"
  "$PYTHON" -m venv .venv 2>/dev/null || {
    # some distros ship venv without ensurepip; try bootstrapping
    "$PYTHON" -m venv .venv --without-pip && ./.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 \
      || { echo "ERROR: venv creation failed. On Debian/Ubuntu: sudo apt install python3-venv python3-full" >&2; exit 1; }
  }
fi

# 2 · dependencies
echo "==> installing dependencies (tvdatafeed-enhanced, websocket-client, pandas)"
./.venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade pip
./.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
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
