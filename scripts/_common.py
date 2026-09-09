"""Shared plumbing for dse-data helper scripts.

Import `dse` from the skill root (venv re-exec, scanner retries, tvdatafeed fetch).
Keep helper output COMPACT: markdown tables by default (token-lean for LLM context),
JSON/CSV only when asked.
"""
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

import dse  # noqa: E402  (skill CLI module — reuse scanner + venv plumbing)

INTERVALS = {"1m": "in_1_minute", "5m": "in_5_minute", "15m": "in_15_minute",
             "30m": "in_30_minute", "1h": "in_1_hour", "2h": "in_2_hour",
             "4h": "in_4_hour", "1D": "in_daily", "1W": "in_weekly", "1M": "in_monthly"}
PERIOD_BARS = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126,
               "1y": 252, "2y": 504, "3y": 756, "5y": 1260, "max": 1200}


def ensure_venv():
    dse.ensure_venv()


def parse_symbols(raw):
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def resolve_bars(period, bars):
    """Validate inputs and return the bar count. Exits with a clean error on bad input."""
    if bars is not None:
        if not 1 <= bars <= 5000:
            sys.exit("error: --bars must be 1-5000 (got %d)" % bars)
        return bars
    p = (period or "1y").lower()
    if p not in PERIOD_BARS:
        sys.exit("error: --period must be one of %s (got %r)" % (", ".join(PERIOD_BARS), period))
    return PERIOD_BARS[p]


def md_table(header, rows, aligns=None):
    """Compact markdown table. rows = list of lists of strings."""
    out = ["| " + " | ".join(header) + " |"]
    aligns = aligns or ["---"] * len(header)
    out.append("| " + " | ".join(aligns) + " |")
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def emit(md=None, data=None, fmt="md", json_key="data"):
    """Print in the requested format. md is a string; data is the JSON structure."""
    if fmt == "json":
        print(json.dumps(data, indent=1, ensure_ascii=False))
    elif fmt == "csv":
        rows = data.get(json_key) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            for k, v in rows.items():
                print(f"{k}\t{json.dumps(v, ensure_ascii=False)}")
        elif rows:
            header = list(rows[0].keys())
            print("\t".join(header))
            for r in rows:
                print("\t".join(str(r.get(h, "")) for h in header))
    else:
        print(md if md else json.dumps(data, ensure_ascii=False))
