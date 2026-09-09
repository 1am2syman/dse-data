# Output Contract — dse-data CLI

The contract every consumer (human, script, or LLM agent) can rely on.

## Streams & exit codes

| stream | carries |
|---|---|
| **stdout** | data only — JSON (pretty, UTF-8) or ASCII chart. Always machine-parseable. |
| **stderr** | diagnostics only — `warning:` lines (non-fatal), `error:` line (fatal), `[dse]` verbose logs |

| exit code | meaning |
|---|---|
| `0` | success (warnings may still have been printed to stderr) |
| `1` | error — single line starting with `error:` on stderr; stdout is **empty or valid partial data** |

Library chatter from `tvdatafeed` (banners, websocket noise) is captured and routed to
stderr — stdout never contains it.

## JSON envelopes

**`snapshot`** → `{as_of, market, count, note, stocks:[…]}` — `stocks[i]` keys are the
field names in [FIELDS.md](FIELDS.md); `ticker` (not `name`); NaN/Inf → `null`.

**`history SYMBOL`** → `{symbol: "DSEBD:SYM", interval, bars, adjustment:"splits",
data:[{datetime, open, high, low, close, volume}, …]}` — bars oldest→newest; integers
stay integers.

**`index`** → `{as_of, indices:[{index:"DSEX"|"DSES", close, change, open, high, low}]}`.

**`chart`** → ASCII only (title, labeled axis, min/max/first/last annotations). Not JSON.

## Global flags

- `--version` — print version, exit 0
- `--verbose` / `-v` — `[dse]` diagnostics to stderr (retries, cache hits/stores)
- `--no-cache` — bypass the cache for this invocation

## Caching

Scanner responses (snapshot/index/technicals/fundamentals) are cached in `cache/`
with a **60s TTL** (index 30s), keyed by request payload, written atomically.
Repeated calls within the TTL are instant and hit no network. History is not cached
(varied parameters). `cache/` is disposable — delete freely.

## Retry & rate-limit behavior

- Scanner: 3 attempts, exponential backoff + jitter (1.5s → 3s → …).
- **HTTP 429 → immediate exit** with a specific message (wait ~60s). The snapshot
  fetches the *entire market in one request* — per-symbol polling is unnecessary and
  rate-limit-hostile.
- History (websocket): 3 attempts via `tvdatafeed-enhanced`, 1.5s between tries.
- Timeouts: 30s per HTTP request.

## Input validation (fails fast, before any network)

- `--bars`: 1–5000 · `--top`: 1–350 · interval: whitelist per command ·
  helper `--period`: whitelist (`1w 2w 1m 3m 6m 1y 2y 3y 5y max`)
- Unknown tickers: snapshot → stderr warning, empty/clean output, exit 0 ·
  history → `error: no data for …` exit 1

## Environment

- Python ≥ 3.9 (guarded at startup with a clear message).
- `history`/`chart` auto re-exec into the skill venv (`.venv/`) if deps are missing —
  the caller's interpreter choice doesn't matter for those commands.
