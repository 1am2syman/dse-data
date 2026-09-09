#!/usr/bin/env python3
"""fundamentals.py — fundamental data for DSE tickers from the TradingView snapshot.

One scanner call covers any number of tickers. Note: DSE fundamental coverage is
partial upstream (e.g. P/E on ~half the board; no beta/debt-ratio for DSE) —
nulls are absent upstream, not a bug. Fields with no data are dropped per ticker.

Examples:
    fundamentals.py GP,EBL,SQURPHARMA
    fundamentals.py BRACBANK --format json
"""
import datetime as dt

import _common as C
import dse

FUNDS = ["market_cap_basic", "price_earnings_ttm", "earnings_per_share_basic_ttm",
         "total_revenue_ttm", "net_income_ttm", "price_book_ratio",
         "dividends_yield_current", "total_shares_outstanding_fundamental",
         "current_ratio", "number_of_employees", "price_free_cash_flow_ttm",
         "sector", "industry"]
HUMAN = {"market_cap_basic": "market cap (BDT)", "price_earnings_ttm": "P/E (TTM)",
         "earnings_per_share_basic_ttm": "EPS (TTM)", "total_revenue_ttm": "revenue (TTM)",
         "net_income_ttm": "net income (TTM)", "price_book_ratio": "P/B",
         "dividends_yield_current": "dividend yield %", "total_shares_outstanding_fundamental": "shares out",
         "current_ratio": "current ratio", "number_of_employees": "employees",
         "price_free_cash_flow_ttm": "P/FCF", "sector": "sector", "industry": "industry"}


def human_num(v):
    if v is None: return "—"
    if isinstance(v, str): return v
    for div, suf in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(v) >= div: return f"{v/div:,.1f}{suf}"
    return f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="fundamentals for DSE tickers")
    ap.add_argument("symbols", help="comma-separated bare tickers")
    ap.add_argument("--format", default="md", choices=["md", "json", "csv"])
    args = ap.parse_args()

    symbols = C.parse_symbols(args.symbols)
    rows = dse.scan_rows(["name"] + FUNDS)
    picked, missing = [], set(symbols)
    for r in rows:
        if r["ticker"] in missing:
            picked.append(r); missing.discard(r["ticker"])
    if missing:
        print(f"warning: not found: {', '.join(sorted(missing))}", file=sys.stderr)

    out = {"as_of": dt.datetime.now(dt.timezone.utc).isoformat(), "stocks": []}
    for r in picked:
        d = {HUMAN[k]: (round(r[k], 2) if isinstance(r.get(k), float) else r.get(k))
             for k in FUNDS if r.get(k) is not None}
        d = {"ticker": r["ticker"], **d}
        out["stocks"].append(d)

    if args.format == "md":
        tickers = [s["ticker"] for s in out["stocks"]]
        md = f"DSE fundamentals · as of {out['as_of'][:16]}Z · nulls omitted (absent upstream for DSE)\n\n"
        fields = [HUMAN[k] for k in FUNDS]
        md += C.md_table(["field"] + tickers,
                         [[f] + [human_num(next((s.get(f) for s in out["stocks"] if s["ticker"] == tk), None)) for tk in tickers]
                          for f in fields])
    else:
        md = None
    C.emit(md=md, data=out, fmt=args.format, json_key="stocks")


if __name__ == "__main__":
    main()
