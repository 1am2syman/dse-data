#!/usr/bin/env python3
"""backfill.py — bulk-download daily/intraday history for a list of DSE symbols.

Uses the dse-data CLI (same venv) and writes one JSON file per symbol into --out.

Usage (run with the skill's venv python):
    backfill.py --symbols GP,SQURPHARMA,BRACBANK [--interval 1D] [--bars 1200] [--out data]
"""
import argparse
import json
import os
import subprocess
import sys
import time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSE = os.path.join(SKILL_DIR, "dse.py")


def main():
    ap = argparse.ArgumentParser(description="bulk history download for DSE symbols")
    ap.add_argument("--symbols", required=True, help="comma-separated bare tickers, e.g. GP,SQURPHARMA")
    ap.add_argument("--interval", default="1D",
                    help="1m 5m 15m 30m 1h 2h 4h 1D 1W 1M (default 1D)")
    ap.add_argument("--bars", type=int, default=1200, help="bar count (1-5000, default 1200)")
    ap.add_argument("--skip-existing", action="store_true", help="skip symbols whose output file already exists")
    ap.add_argument("--out", default="data", help="output directory (default ./data)")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if not (1 <= a.bars <= 5000):
        sys.exit("error: --bars must be 1-5000 (got %d)" % a.bars)
    ok = fail = skipped = 0
    for i, t in enumerate(symbols):
        dest = os.path.join(a.out, f"{t}_{a.interval}.json")
        if a.skip_existing and os.path.exists(dest):
            skipped += 1
            print(f"↷ {t}: {dest} exists, skipping")
            continue
        r = subprocess.run([sys.executable, DSE, "history", t,
                            "--interval", a.interval, "--bars", str(a.bars)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            try:
                json.loads(r.stdout)  # validate
                tmp = dest + ".tmp"
                with open(tmp, "w") as f:
                    f.write(r.stdout)
                os.replace(tmp, dest)  # atomic: no partial files on crash
                ok += 1
                print(f"✓ {t}: {os.path.getsize(dest)} bytes -> {dest}")
            except json.JSONDecodeError:
                fail += 1
                print(f"✗ {t}: invalid JSON (stderr: {r.stderr.strip()[:120]})")
        else:
            fail += 1
            print(f"✗ {t}: {r.stderr.strip()[:160]}")
        if i < len(symbols) - 1:
            time.sleep(0.5)  # rate etiquette
    print(f"\ndone: {ok} ok, {fail} failed, {skipped} skipped -> {os.path.abspath(a.out)}")
    sys.exit(1 if fail and not ok else 0)


if __name__ == "__main__":
    main()
