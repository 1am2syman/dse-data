#!/usr/bin/env bash
# Live smoke test — verifies real data flow (needs internet + TradingView reachable).
# Run from the repo root with the venv:  ./.venv/bin/python tests/smoke_live.sh  (or bash it)
# NOT run in CI (CI is offline-only); use after install or before release.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-./.venv/bin/python}"
[ -x "$PY" ] || PY=python3

fail() { echo "✗ $1" >&2; exit 1; }

echo "1/6 index";       $PY dse.py index | grep -q DSEX || fail "index"
echo "2/6 snapshot";    $PY dse.py snapshot --top 3 | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['count']==3" || fail "snapshot"
echo "3/6 history";     $PY dse.py history GP --bars 3 | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['bars']==3 and d['data'][-1]['close']>0" || fail "history"
echo "4/6 technicals";  $PY scripts/technicals.py GP | grep -q "^| GP" || fail "technicals"
echo "5/6 fundamentals"; $PY scripts/fundamentals.py GP | grep -q "market cap" || fail "fundamentals"
echo "6/6 price";       $PY scripts/price.py GP --period 1w | grep -q "^| GP" || fail "price"
echo "✓ all live smoke tests passed"
