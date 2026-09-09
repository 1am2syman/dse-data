#!/usr/bin/env python3
"""dse.py — Dhaka Stock Exchange data CLI for LLM agents.

Sources (keyless):
  - scanner.tradingview.com/bangladesh/scan  (market-wide snapshot)
  - data.tradingview.com websocket via tvdatafeed-enhanced (historical OHLCV)

All commands print JSON to stdout (chart prints ASCII). Errors go to stderr, exit 1.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request

if sys.version_info < (3, 9):
    sys.exit("error: dse-data requires Python 3.9+ (you have %d.%d)" % sys.version_info[:2])

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SCANNER_URL = "https://scanner.tradingview.com/bangladesh/scan"
EXCHANGE = "DSEBD"
__version__ = "1.1.2"
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv   # peek: diagnostics before parsing
NO_CACHE = "--no-cache" in sys.argv
CACHE_DIR = os.path.join(SKILL_DIR, "cache")
SCAN_TTL = 60  # seconds: whole-market snapshot responses are effectively frozen for a minute

CORE_COLS = [
    "name", "description", "close", "open", "high", "low", "change", "change_abs",
    "volume", "average_volume_10d_calc", "relative_volume_10d_calc", "gap",
    "change_from_open", "market_cap_basic", "price_earnings_ttm", "sector", "industry",
    "RSI", "SMA50", "SMA200", "Recommend.All",
    "price_52_week_high", "price_52_week_low", "Perf.W", "Perf.1M", "Perf.YTD",
]
FULL_EXTRA_COLS = [
    "MACD.macd", "MACD.signal", "Stoch.K", "Stoch.D", "ADX", "ATR", "Mom", "W.R",
    "BB.upper", "BB.lower", "EMA10", "EMA20", "EMA50", "SMA10", "SMA20",
    "Recommend.MA", "Recommend.Other", "Volatility.D",
    "dividends_yield_current", "earnings_per_share_basic_ttm", "total_revenue_ttm",
    "net_income_ttm", "price_book_ratio", "total_shares_outstanding_fundamental",
    "current_ratio", "number_of_employees", "price_free_cash_flow_ttm",
]
INDEX_TICKERS = ["DSEBD:DSEX", "DSEBD:DSES"]


def ensure_venv():
    """Re-exec into the skill venv if tvDatafeed is missing (needed for history)."""
    try:
        import tvDatafeed  # noqa: F401
    except ImportError:
        venv_py = os.path.join(SKILL_DIR, ".venv", "bin", "python")
        if os.path.exists(venv_py) and not os.environ.get("DSE_VENV_REEXEC"):
            env = dict(os.environ, DSE_VENV_REEXEC="1", VIRTUAL_ENV=SKILL_DIR + "/.venv")
            os.execve(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:], env)
        sys.exit("error: tvdatafeed-enhanced missing. Run:\n"
                 "  python3 -m venv %s/.venv && %s/.venv/bin/pip install tvdatafeed-enhanced websocket-client"
                 % (SKILL_DIR, SKILL_DIR))


class CaptureStdout:
    """Keep library chatter (banners, websocket noise) away from stdout JSON."""
    def __enter__(self):
        import io
        self._old, self.buf = sys.stdout, io.StringIO()
        sys.stdout = self.buf
        return self
    def __exit__(self, *a):
        sys.stdout = self._old
        noise = self.buf.getvalue().strip()
        if noise:
            print(noise, file=sys.stderr)


def fetch_hist(symbol, interval_enum, bars, attempts=3):
    """Fetch bars via tvdatafeed with retries; returns DataFrame or None."""
    ensure_venv()
    from tvDatafeed import TvDatafeed
    for i in range(attempts):
        try:
            with CaptureStdout():
                tv = TvDatafeed()
                df = tv.get_hist(symbol, EXCHANGE, interval=interval_enum, n_bars=bars)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print("warning: attempt %d failed: %s" % (i + 1, e), file=sys.stderr)
        time.sleep(1.5)
    return None


def _log(msg):
    if VERBOSE:
        print("[dse] %s" % msg, file=sys.stderr)


def cache_get(key, ttl):
    if NO_CACHE:
        return None
    path = os.path.join(CACHE_DIR, key + ".json")
    try:
        if time.time() - os.path.getmtime(path) < ttl:
            _log("cache hit: %s" % key)
            return open(path).read()
    except OSError:
        pass
    return None


def cache_put(key, text):
    if NO_CACHE:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, key + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, path)  # atomic
        _log("cache store: %s" % key)
    except OSError as e:
        _log("cache write failed (non-fatal): %s" % e)


def http_scan(payload, ttl=SCAN_TTL):
    """POST to the scanner with backoff+jitter, 429 detection, and TTL cache.
    Returns parsed JSON body; exits(1) with a specific message on failure."""
    key = "scan_" + hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    cached = cache_get(key, ttl)
    if cached is not None:
        return json.loads(cached)
    data = json.dumps(payload).encode()
    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(
            SCANNER_URL, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode()
                cache_put(key, text)
                return json.loads(text)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sys.exit("error: TradingView rate-limited us (HTTP 429). Wait ~60s, "
                         "or run fewer calls; snapshot covers the whole market in one request.")
            last_err = e
        except Exception as e:
            last_err = e
        if attempt < 2:
            delay = 1.5 * (2 ** attempt) + random.uniform(0, 0.75)
            _log("retry %d/2 in %.1fs (%s)" % (attempt + 1, delay, last_err))
            time.sleep(delay)
    sys.exit("error: scanner request failed after 3 attempts: %s" % last_err)


def scan(columns, sort=None, order="desc"):
    payload = {
        "filter": [{"left": "type", "operation": "equal", "right": "stock"}],
        "columns": columns,
        "sort": {"sortBy": sort or "name", "sortOrder": order},
    }
    return http_scan(payload)


def scan_rows(columns):
    body = scan(columns)
    rows = []
    for r in body.get("data", []):
        d = r.get("d", [])
        row = {}
        for i, c in enumerate(columns):
            v = d[i] if i < len(d) else None
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                v = None
            row[c] = v
        row["ticker"] = row.pop("name")
        rows.append(row)
    return rows


def out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_snapshot(args):
    cols = CORE_COLS + (FULL_EXTRA_COLS if args.full else [])
    rows = scan_rows(cols)
    if args.symbol:
        want = [s.strip().upper() for s in args.symbol.split(",")]
        rows = [r for r in rows if r["ticker"] in want]
        missing = set(want) - {r["ticker"] for r in rows}
        if missing:
            print("warning: not found: %s" % ", ".join(sorted(missing)), file=sys.stderr)
    keymap = {
        "volume": "volume", "gainers": "change", "losers": "change",
        "marketcap": "market_cap_basic", "rsi": "RSI", "relvol": "relative_volume_10d_calc",
    }
    sort_key, reverse = keymap.get(args.by, "volume"), args.by != "losers"
    rows.sort(key=lambda r: (r.get(sort_key) is None, r.get(sort_key) or 0), reverse=reverse)
    if args.top:
        rows = rows[:args.top]
    out({
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
        "market": "DSE (Bangladesh)", "count": len(rows),
        "note": "delayed anonymous feed; nulls = field absent upstream for DSE",
        "stocks": rows,
    })


def cmd_history(args):
    intervals = {"1m": "in_1_minute", "5m": "in_5_minute", "15m": "in_15_minute",
                 "30m": "in_30_minute", "1h": "in_1_hour", "2h": "in_2_hour",
                 "4h": "in_4_hour", "1D": "in_daily", "1W": "in_weekly", "1M": "in_monthly"}
    if args.interval not in intervals:
        sys.exit("error: interval must be one of %s" % ", ".join(intervals))
    ensure_venv()
    from tvDatafeed import Interval
    df = fetch_hist(args.symbol.upper(), getattr(Interval, intervals[args.interval]), args.bars)
    if df is None:
        sys.exit("error: no data for %s (check ticker; use bare symbol like GP or SQURPHARMA)" % args.symbol)
    bars = []
    for ts, row in df.iterrows():
        def num(v):
            v = float(v)
            return None if math.isnan(v) else (int(v) if v == int(v) else round(v, 6))
        bars.append({"datetime": ts.isoformat(), "open": num(row["open"]),
                     "high": num(row["high"]), "low": num(row["low"]),
                     "close": num(row["close"]), "volume": num(row["volume"])})
    out({"symbol": "%s:%s" % (EXCHANGE, args.symbol.upper()), "interval": args.interval,
         "bars": len(bars), "adjustment": "splits", "data": bars})


def cmd_index(args):
    cols = ["name", "close", "change", "open", "high", "low"]
    payload = {"symbols": {"tickers": INDEX_TICKERS, "query": {"types": []}}, "columns": cols}
    body = http_scan(payload, ttl=30)
    out({"as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
         "indices": [dict({"index": t.split(":")[1]},
                          **{cols[i]: (item["d"][i] if i < len(item.get("d", [])) else None)
                             for i in range(len(cols))})
                     for t, item in zip(INDEX_TICKERS, body.get("data", []))]})


def render_chart(dates, closes, title):
    n = len(closes)
    W, H, TICKS = 108, 18, 5
    lo, hi = min(closes), max(closes)
    pad = (hi - lo) * 0.08 or 1
    lo_s, hi_s = lo - pad, hi + pad
    def ypos(p): return round((hi_s - p) / (hi_s - lo_s) * (H - 1))
    grid = [[" "] * W for _ in range(H)]
    colsw = [round(i * (W - 1) / (n - 1)) for i in range(n)]
    for i in range(n - 1):
        c0, c1, p0, p1 = colsw[i], colsw[i + 1], closes[i], closes[i + 1]
        for c in range(c0, c1):
            f = (c - c0) / (c1 - c0)
            grid[ypos(p0 + f * (p1 - p0))][c] = "·"
    for i, c in enumerate(colsw):
        grid[ypos(closes[i])][c] = "●"
    marks = {0: "%.1f" % closes[0], n - 1: "%.1f" % closes[-1],
             closes.index(lo): "low %.1f" % lo, closes.index(hi): "high %.1f" % hi}
    for i, text in marks.items():
        y, c = ypos(closes[i]), colsw[i]
        start = max(0, min(c - 2, W - len(text) - 1))
        ty = y - 1 if y > 0 else y + 1
        grid[ty][start:start + len(text)] = list(text)
    print(title)
    print("─" * (W + 9))
    for r in range(H):
        p = hi_s - r * (hi_s - lo_s) / (H - 1)
        lab = "%6.1f ┤" % p if r % (H // TICKS) == 0 or r == H - 1 else "       │"
        print(lab + "".join(grid[r]).rstrip())
    xlab = [" "] * (W + 8)
    for i in range(n):
        if i % max(1, n // 6) == 0 or i == n - 1:
            s = dates[i]
            st = max(0, min(colsw[i] - 2, W + 8 - len(s)))
            xlab[st:st + len(s)] = list(s)
    print("       " + "".join(xlab).rstrip())


def cmd_chart(args):
    intervals = {"1m": "in_1_minute", "5m": "in_5_minute", "15m": "in_15_minute",
                 "30m": "in_30_minute", "1h": "in_1_hour", "1D": "in_daily", "1W": "in_weekly"}
    if args.interval not in intervals:
        sys.exit("error: chart interval must be one of %s" % ", ".join(intervals))
    ensure_venv()
    from tvDatafeed import Interval
    df = fetch_hist(args.symbol.upper(), getattr(Interval, intervals[args.interval]), args.bars)
    if df is None:
        sys.exit("error: no data for %s" % args.symbol)
    dates = [ts.strftime("%d %b %H:%M" if args.interval != "1D" else "%d %b") for ts in df.index]
    closes = [float(c) for c in df["close"]]
    period = (closes[-1] / closes[0] - 1) * 100
    title = ("%s — DSE %s close, last %d bars · last %.1f (%+.2f%% over period) · split-adjusted BDT"
             % (args.symbol.upper(), args.interval, n := len(closes), closes[-1], period))
    render_chart(dates, closes, title)


def main():
    ap = argparse.ArgumentParser(prog="dse.py", description="Dhaka Stock Exchange data (TradingView, keyless)")
    ap.add_argument("--version", action="version", version="dse-data %s" % __version__)
    ap.add_argument("--verbose", "-v", action="store_true", help="diagnostics to stderr (retries, cache)")
    ap.add_argument("--no-cache", action="store_true", help="bypass the %ds scanner cache" % SCAN_TTL)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("snapshot", help="market-wide snapshot JSON")
    p.add_argument("--top", type=int, help="limit to N results (1-350)")
    p.add_argument("--by", default="volume",
                   choices=["volume", "gainers", "losers", "marketcap", "rsi", "relvol"])
    p.add_argument("--symbol", help="filter by ticker(s), comma-separated (bare symbols)")
    p.add_argument("--full", action="store_true", help="include all technicals + fundamentals")

    p = sub.add_parser("history", help="historical OHLCV bars as JSON")
    p.add_argument("symbol")
    p.add_argument("--interval", default="1D")
    p.add_argument("--bars", type=int, default=100)

    p = sub.add_parser("chart", help="ASCII chart of closes")
    p.add_argument("symbol")
    p.add_argument("--interval", default="1D")
    p.add_argument("--bars", type=int, default=30)

    sub.add_parser("index", help="DSEX / DSES index values")
    args = ap.parse_args()
    if hasattr(args, "bars") and not 1 <= args.bars <= 5000:
        sys.exit("error: --bars must be 1-5000 (got %d)" % args.bars)
    if hasattr(args, "top") and args.top is not None and not 1 <= args.top <= 350:
        sys.exit("error: --top must be 1-350 (got %d)" % args.top)
    {"snapshot": cmd_snapshot, "history": cmd_history,
     "chart": cmd_chart, "index": cmd_index}[args.cmd](args)


if __name__ == "__main__":
    main()
