#!/usr/bin/env python3
"""technicals.py — current TradingView technical indicators for DSE tickers.

One scanner call covers any number of tickers. Output is a compact markdown
table by default (token-lean); --format json for structured data; --raw adds
every raw field.

Examples:
    technicals.py GP,BRACBANK,SHAHJABANK
    technicals.py GP --format json
"""
import datetime as dt

import _common as C
import dse

CORE = ["name", "close", "change", "RSI", "MACD.macd", "MACD.signal", "Stoch.K", "ADX",
        "ATR", "SMA50", "SMA200", "EMA20", "Recommend.All", "relative_volume_10d_calc",
        "price_52_week_high", "price_52_week_low", "Volatility.D"]
EXTRA = ["Mom", "W.R", "BB.upper", "BB.lower", "EMA10", "EMA50", "SMA10", "SMA20",
         "Recommend.MA", "Recommend.Other", "gap", "change_from_open",
         "Perf.W", "Perf.1M", "Perf.YTD", "average_volume_10d_calc", "volume"]


def plain_read(s):
    """Plain-words read of the indicator stack, for LLM consumption."""
    bits = []
    rsi = s.get("RSI")
    if rsi is not None:
        if rsi <= 30: bits.append("oversold")
        elif rsi >= 70: bits.append("overbought")
        elif rsi >= 45: bits.append("momentum ok")
        else: bits.append("soft momentum")
    if s.get("MACD.macd") is not None and s.get("MACD.signal") is not None:
        bits.append("MACD rising" if s["MACD.macd"] > s["MACD.signal"] else "MACD falling")
    if s.get("ADX") is not None:
        bits.append("no trend (range-friendly)" if s["ADX"] < 20 else
                    ("trending" if s["ADX"] > 30 else "mild trend"))
    c, s50, s200 = s.get("close"), s.get("SMA50"), s.get("SMA200")
    if c and s50 and s200:
        bits.append("above 50d" if c > s50 else "below 50d")
        bits.append("above 200d" if c > s200 else "below 200d")
    if s.get("Recommend.All") is not None:
        r = s["Recommend.All"]
        bits.append("TV rating: buy-side" if r > 0.1 else ("TV rating: sell-side" if r < -0.1 else "TV rating: neutral"))
    return " · ".join(bits)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="TradingView technical indicators for DSE tickers")
    ap.add_argument("symbols", help="comma-separated bare tickers")
    ap.add_argument("--format", default="md", choices=["md", "json", "csv"])
    ap.add_argument("--raw", action="store_true", help="include every raw indicator field")
    args = ap.parse_args()

    symbols = C.parse_symbols(args.symbols)
    cols = CORE + (EXTRA if args.raw else [])
    rows = dse.scan_rows(cols)
    picked, missing = [], set(symbols)
    for r in rows:
        if r["ticker"] in missing:
            picked.append(r); missing.discard(r["ticker"])
    if missing:
        print(f"warning: not found: {', '.join(sorted(missing))}", file=sys.stderr)

    out_rows = []
    for r in picked:
        def g(k):
            v = r.get(k)
            return round(v, 2) if isinstance(v, float) else v
        macd_state = ("rising" if (r.get("MACD.macd") or 0) > (r.get("MACD.signal") or 0) else "falling") if r.get("MACD.macd") is not None else None
        lo, hi = r.get("price_52_week_low"), r.get("price_52_week_high")
        pos52 = round((r["close"]-lo)/(hi-lo)*100) if lo and hi and hi > lo else None
        vs200 = round((r["close"]/r["SMA200"]-1)*100, 1) if r.get("close") and r.get("SMA200") else None
        row = {"ticker": r["ticker"], "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
               "close": g("close"), "change_pct": g("change"), "RSI": g("RSI"),
               "MACD": g("MACD.macd"), "MACD_signal": g("MACD.signal"), "MACD_state": macd_state,
               "Stoch_K": g("Stoch.K"), "ADX": g("ADX"), "ATR": g("ATR"),
               "vs_SMA50_pct": round((r["close"]/r["SMA50"]-1)*100, 1) if r.get("close") and r.get("SMA50") else None,
               "vs_SMA200_pct": vs200, "position_in_52w_band_pct": pos52,
               "rel_volume_10d": g("relative_volume_10d_calc"), "vol_daily_pct": g("Volatility.D"),
               "TV_rating": g("Recommend.All"), "read": plain_read(r)}
        if args.raw:
            row["raw"] = {k: g(k) for k in EXTRA}
        out_rows.append(row)

    md = C.md_table(
        ["ticker", "close", "RSI", "MACD", "Stoch", "ADX", "vs 50d", "vs 200d", "52w pos", "rel vol", "TV", "read"],
        [[r["ticker"], r["close"], r["RSI"], r["MACD_state"], r["Stoch_K"], r["ADX"],
          (f"{r['vs_SMA50_pct']:+.0f}%" if r["vs_SMA50_pct"] is not None else "—"),
          (f"{r['vs_SMA200_pct']:+.0f}%" if r["vs_SMA200_pct"] is not None else "—"),
          (f"{r['position_in_52w_band_pct']}%" if r["position_in_52w_band_pct"] is not None else "—"),
          (f"{r['rel_volume_10d']:.1f}x" if r["rel_volume_10d"] else "—"),
          (f"{r['TV_rating']:+.2f}" if r["TV_rating"] is not None else "—"),
          r["read"]] for r in out_rows])
    md += "\nRSI <30 oversold / >70 overbought · MACD rising/falling = momentum · ADX <20 no trend (range-friendly) · TV = TradingView composite rating (−1…+1)"
    data = {"as_of": dt.datetime.now(dt.timezone.utc).isoformat(), "count": len(out_rows), "stocks": out_rows}
    C.emit(md=md, data=data, fmt=args.format, json_key="stocks")


if __name__ == "__main__":
    main()
