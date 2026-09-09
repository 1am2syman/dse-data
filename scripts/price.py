#!/usr/bin/env python3
"""price.py — price history for DSE tickers, period-based, context-lean.

Examples:
    price.py GP,SQURPHARMA                       # 1y summary, markdown
    price.py GP --period 6m --series             # + downsampled OHLCV series
    price.py GP,BRACBANK --period 1y --format json
"""
import argparse
import datetime as dt
import sys

import _common as C
import dse


def main():
    ap = argparse.ArgumentParser(description="price history for DSE tickers (context-lean)")
    ap.add_argument("symbols", help="comma-separated bare tickers, e.g. GP,SQURPHARMA")
    ap.add_argument("--period", default="1y", help="1w 2w 1m 3m 6m 1y 2y 3y 5y max (default 1y)")
    ap.add_argument("--interval", default="1D", help="1m 5m 15m 30m 1h 2h 4h 1D 1W 1M")
    ap.add_argument("--bars", type=int, help="override --period with an exact bar count")
    ap.add_argument("--series", action="store_true", help="include downsampled OHLCV series")
    ap.add_argument("--format", default="md", choices=["md", "json", "csv"])
    a = ap.parse_args()

    C.ensure_venv()
    from tvDatafeed import Interval

    symbols = C.parse_symbols(a.symbols)
    interval = C.INTERVALS.get(a.interval)
    if not interval:
        sys.exit(f"error: interval must be one of {', '.join(C.INTERVALS)}")
    bars = C.resolve_bars(a.period, a.bars)

    out = {"as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
           "interval": a.interval, "period": a.period, "stocks": []}
    md_rows = []
    for t in symbols:
        df = dse.fetch_hist(t, getattr(dse.Interval if False else Interval, interval), bars)
        if df is None or df.empty:
            md_rows.append([t, "no data", "", "", "", ""]); continue
        closes = [float(c) for c in df["close"]]
        dates = [ts.strftime("%Y-%m-%d") for ts in df.index]
        last = closes[-1]
        def ret(n):
            return f"{(last/closes[-1-n]-1)*100:+.1f}%" if len(closes) > n else "—"
        row = {"ticker": t, "name": f"{t}", "from": dates[0], "to": dates[-1],
               "close": round(last, 2), "period_change_pct": round((last/closes[0]-1)*100, 1),
               "high": round(max(float(h) for h in df["high"]), 2),
               "low": round(min(float(l) for l in df["low"]), 2),
               "last_volume": int(df["volume"].iloc[-1] or 0),
               "returns": {"5d": float(ret(5).rstrip("%")) if ret(5) != "—" else None,
                           "21d": float(ret(21).rstrip("%")) if ret(21) != "—" else None,
                           "63d": float(ret(63).rstrip("%")) if ret(63) != "—" else None,
                           "126d": float(ret(126).rstrip("%")) if ret(126) != "—" else None},
               "closes": closes, "dates": dates}
        if a.series:
            step = max(1, len(closes)//60)
            row["series"] = [{"date": dates[i], "open": round(float(df['open'].iloc[i]), 2),
                              "high": round(float(df['high'].iloc[i]), 2),
                              "low": round(float(df['low'].iloc[i]), 2),
                              "close": round(closes[i], 2),
                              "volume": int(df['volume'].iloc[i] or 0)}
                             for i in range(0, len(closes), step)]
            if dates[-1] not in [s["date"] for s in row["series"]]:
                i = len(closes) - 1
                row["series"].append({"date": dates[i], "open": round(float(df['open'].iloc[i]), 2),
                                      "high": round(float(df['high'].iloc[i]), 2),
                                      "low": round(float(df['low'].iloc[i]), 2),
                                      "close": round(closes[i], 2), "volume": int(df['volume'].iloc[i] or 0)})
        out["stocks"].append(row)
        rets = " · ".join(f"{lbl} {ret(n)}" for lbl, n in [("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126)] if len(closes) > n)
        md_rows.append([t, f"{last:.1f}", f"{(last/closes[0]-1)*100:+.1f}%",
                        f"{max(float(h) for h in df['high']):.1f}", f"{min(float(l) for l in df['low']):.1f}", rets])

    md = None
    if a.format == "md":
        md = (f"DSE prices · {a.interval} bars · period {a.period} ({bars} bars) · as of {out['as_of'][:16]}Z\n"
              + C.md_table(["ticker", "close", "period", "high", "low", "returns"], md_rows)
              + "\nreturns = 1w / 1m / 3m / 6m where available")
    C.emit(md=md, data=out, fmt=a.format, json_key="stocks")


if __name__ == "__main__":
    main()
