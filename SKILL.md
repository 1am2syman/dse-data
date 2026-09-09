---
name: dse-data
description: Dhaka Stock Exchange (DSE/Bangladesh) market data for analysis - live market-wide snapshots with technicals and fundamentals, historical OHLCV bars (daily and intraday), index values, and ASCII charts. Use when the user asks about DSE, DSEX, Bangladesh stocks, Dhaka Stock Exchange prices, or trends in DSE-listed companies.
---

# DSE Data

Machine-readable Dhaka Stock Exchange data from TradingView's public endpoints (keyless,
anonymous). Built for LLM-driven analysis: every command outputs clean JSON to stdout
(except `chart`, which renders ASCII).

Repo: https://github.com/1am2syman/dse-data

## Setup

If installed at the standard location (`~/.pi/agent/skills/dse-data`), everything is
already wired — the CLI re-execs into its local `.venv` automatically.

If the venv is missing (fresh clone), run once:

```bash
cd ~/.pi/agent/skills/dse-data && ./setup.sh
```

`setup.sh` creates `.venv` and installs the pinned dependency set
(`requirements-lock.txt`). (`websocket-client` is listed explicitly — the library
needs it but doesn't declare it.)

Runtime flags (any command): `--version` · `--verbose` (retries/cache to stderr) ·
`--no-cache` (bypass the 60s snapshot cache).

## Commands

```bash
D=~/.pi/agent/skills/dse-data/dse.py        # adjust if installed elsewhere

# Whole-market snapshot (350 stocks, 1 call): price + core technicals
$D snapshot                          # JSON, all stocks
$D snapshot --top 20 --by volume     # ranked: volume|gainers|losers|marketcap|rsi|relvol
$D snapshot --symbol GP              # single symbol (comma-separate for several)
$D snapshot --full                   # + all technical indicators & fundamental fields

# Historical bars (split-adjusted OHLCV, up to ~5000/request)
$D history SQURPHARMA --interval 1D --bars 30
$D history GP --interval 5m --bars 500      # intraday: 1m 5m 15m 30m 1h 2h 4h 1D 1W 1M

# ASCII line chart with data labels (human-readable sanity check)
$D chart SQURPHARMA --interval 1D --bars 30

# Index values
$D index                             # DSEX and DSES levels

# Fundamentals for specific symbols
$D snapshot --symbol GP,BATBC --full | jq '.stocks'
```

Helper scripts (`scripts/`, run with the skill's venv python) — **prefer these over raw
`snapshot --full` / `history` dumps when studying specific tickers**: same answer,
~50× fewer tokens. All take comma-separated tickers and human periods, one network
call wherever possible:

```bash
P=~/.pi/agent/skills/dse-data/.venv/bin/python
S=~/.pi/agent/skills/dse-data

$P $S/scripts/price.py GP,SQURPHARMA                     # 1y price summary (md table)
$P $S/scripts/price.py GP --period 6m --series           # + downsampled OHLCV (≤60 rows)
$P $S/scripts/technicals.py GP,BRACBANK,SHAHJABANK       # current indicators + plain-words read
$P $S/scripts/fundamentals.py GP,EBL,SQURPHARMA          # fundamentals table
```

Notes: `--format json|csv` switches output; `--period` accepts 1w/2w/1m/3m/6m/1y/2y/3y/5y/max;
`technicals.py --raw` adds every raw indicator field. Period returns (1w/1m/3m/6m) are
pre-computed in price.py so the agent doesn't recompute from raw bars.

Bulk download:

```bash
$P $S/scripts/backfill.py --symbols GP,SQURPHARMA --interval 1D --bars 1200 --out data/
```

## Data source notes (verified 2026-09)

- **Two endpoints, both keyless:**
  - `scanner.tradingview.com/bangladesh/scan` — market-wide *snapshot*: latest price,
    OHLC, volume, ~20 technical indicators, fundamentals. No history.
  - `data.tradingview.com` websocket (via `tvdatafeed-enhanced`) — historical OHLCV bars.
- **Symbols** use TradingView exchange code `DSEBD:` (e.g. `DSEBD:GP`). The CLI adds it
  automatically; pass the bare ticker.
- **Delay:** anonymous feeds are delayed (typically ~2–15 min). Fine for daily analysis,
  not for scalping.
- **Trading hours:** Sunday–Thursday, 10:00–14:00 BST. Outside hours you get the last
  session's data.
- **Prices are split-adjusted** (TradingView chart default). Re-pull over time; corporate
  actions restate history.
- **Fundamentals coverage is partial for DSE:** P/E ~170/350 stocks, EPS/revenue/net
  income ~230/350, P/B ~258/350. Beta and debt-to-asset are NOT provided for DSE. Empty
  = absent upstream, not a bug.
- **Technicals coverage is complete:** RSI, MACD, Stoch, ADX, ATR, EMAs/SMAs, Bollinger,
  recommendations — 350/350 populated.
- **Intraday history depth:** ~5000 5-min bars per request (≈20 sessions). Daily goes
  back years.
- **News: TradingView does not cover DSE meaningfully.** For price-sensitive disclosures
  (quarterly reports, record dates) use dsebd.org directly.
- **Rate etiquette:** snapshot is 1 HTTP call for the whole market — poll at most ~1/minute.
  Unofficial endpoints; keep scripts resilient (retry once, then report and continue).

## Agent workflow tips

1. `snapshot` gives you the whole market in one shot — filter/judge in context, don't
   loop per-symbol.
2. For trend questions: `history` (daily, 60–120 bars) → compute returns/EMA cross in
   your head or with a quick script, then answer.
3. For intraday questions: `history --interval 5m` (recent sessions only) or `snapshot`
   fields like `gap`, `relative_volume_10d_calc`, `change_from_open`.
4. Use `chart` when you (or the user) want a visual sanity check in the terminal.
5. Cite the vintage: output JSON includes `as_of` timestamps — quote them when
   presenting analysis.
6. Context discipline: use `scripts/price.py`, `technicals.py`, `fundamentals.py` for
   ticker-specific questions (compact tables); reserve `snapshot --full` for whole-market
   scans and raw `history` for when you truly need every bar.
7. Reference docs live in the repo: `docs/FIELDS.md` (every field, unit, and DSE coverage)
   and `docs/CONTRACT.md` (JSON shapes, exit codes, caching, retry behavior).
