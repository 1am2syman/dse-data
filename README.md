# dse-data

A [pi](https://github.com/badlogic/pi) **agent skill** + CLI for Dhaka Stock Exchange
(Bangladesh) market data — built for LLM-driven analysis. Everything is **keyless**:
no API keys, no login, no cost.

## What you get

- `dse.py` — a CLI that outputs clean JSON (or ASCII charts):
  - `snapshot` — all ~350 DSE stocks in one call: price, OHLC, volume, ~20 technical
    indicators (RSI, MACD, Stoch, ADX, EMAs/SMAs, Bollinger, TradingView ratings),
    fundamentals (market cap, P/E, EPS, dividends, …)
  - `history` — daily & intraday OHLCV bars (1m→1M, up to ~5000 bars/request,
    split-adjusted, years deep)
  - `chart` — labeled ASCII charts
  - `index` — DSEX / DSES levels
- `scripts/` — context-lean helper tools (markdown tables by default, JSON/CSV on demand):
  - `price.py` — price history by period (`--period 1y`) with pre-computed returns, optional downsampled series
  - `technicals.py` — current TradingView indicators per ticker + plain-words read (one call for any number of tickers)
  - `fundamentals.py` — fundamentals table per ticker (nulls dropped — DSE coverage is partial upstream)
  - `backfill.py` — bulk-download history into `data/`

## Install (one command, on any pi machine)

```bash
git clone https://github.com/1am2syman/dse-data ~/.pi/agent/skills/dse-data \
  && cd ~/.pi/agent/skills/dse-data && ./setup.sh
```

That's it — the skill auto-registers with pi at the next session start. `setup.sh`
creates `.venv`, installs all dependencies, and smoke-tests a live DSEX pull.

Manual equivalent:

```bash
git clone https://github.com/1am2syman/dse-data ~/.pi/agent/skills/dse-data
cd ~/.pi/agent/skills/dse-data
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
D=~/.pi/agent/skills/dse-data/dse.py

$D snapshot --top 20 --by gainers          # market-wide, one call
$D snapshot --symbol GP --full             # one stock, all fields
$D history SQURPHARMA --interval 1D --bars 30
$D history GP --interval 5m --bars 500
$D chart SQURPHARMA --bars 30              # ASCII chart with labels
$D index                                   # DSEX / DSES
```

In pi, just ask: *"spot trend candidates in DSE banks"* — the skill description
auto-triggers on DSE questions.

Bulk backfill:

```bash
P=~/.pi/agent/skills/dse-data/.venv/bin/python
S=~/.pi/agent/skills/dse-data
$P $S/scripts/backfill.py --symbols GP,SQURPHARMA,BRACBANK --interval 1D --bars 1200 --out data/
```

Context-lean helpers (prefer these when studying specific tickers):

```bash
$P $S/scripts/price.py GP,SQURPHARMA --period 1y
$P $S/scripts/technicals.py GP,BRACBANK,SHAHJABANK
$P $S/scripts/fundamentals.py GP,EBL,SQURPHARMA
```

## Data sources & caveats

- **Prices/technicals/fundamentals:** TradingView public endpoints (Bangladesh scanner
  + chart websocket) via the `tvdatafeed-enhanced` library. Keyless = delayed feed
  (typically 2–15 min). Split-adjusted. Unofficial — resilient-retry is built in, but
  no SLA.
- **Fundamentals for DSE are partial** (e.g. P/E on ~half the board; no beta/debt-ratio).
- **News:** TradingView doesn't cover DSE meaningfully — use dsebd.org disclosures.
- **Trading hours:** Sun–Thu, 10:00–14:00 BST.

## Disclaimer

Analysis tooling, not investment advice. Delayed data. Verify dividends/record dates
via official DSE disclosures before trading.
