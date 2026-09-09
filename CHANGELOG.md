# Changelog

## 1.1.1 — 2026-09-09

**Fixed**
- `history`/`chart` validated `--interval` *after* the venv bootstrap, so on a machine
  without `.venv` a bad interval reported a misleading dependency error. Input
  validation now always precedes environment checks. (Caught by CI on the first run.)

## 1.1.0 — 2026-09-09

Robustness + documentation release.

**Added**
- 60s TTL cache for scanner responses (`cache/`, atomic writes, `--no-cache` bypass)
- `--verbose` diagnostics (retries, cache hits), `--version`
- Input validation before any network call: `--bars` 1–5000, `--top` 1–350, period/interval whitelists
- Offline unit test suite (`tests/test_offline.py`) + GitHub Actions CI (Python 3.9 & 3.12, offline-only)
- Live smoke test script (`tests/smoke_live.sh`) for post-install verification
- Pinned dependency lockfile (`requirements-lock.txt`) — setup.sh prefers it
- Docs: `docs/FIELDS.md` (full data dictionary with DSE coverage), `docs/CONTRACT.md` (output contract, exit codes, caching, retry behavior)
- `backfill.py --skip-existing` (resumable) and atomic file writes
- README troubleshooting table; Python ≥ 3.9 guard in both CLI and setup.sh

**Fixed**
- 429 rate-limit responses now exit immediately with a specific message
- Scanner retries use exponential backoff + jitter (was fixed 1.5s)
- `technicals.py` / `fundamentals.py`: crash (NameError) when warning about unknown tickers

## 1.0.0 — 2026-09-09

Initial release.
- `dse.py` CLI: `snapshot` (whole market, one call), `history` (daily+intraday OHLCV),
  `chart` (ASCII), `index` (DSEX/DSES) — keyless TradingView sources
- Helper scripts: `price.py`, `technicals.py`, `fundamentals.py`, `backfill.py`
- pi agent skill packaging (`SKILL.md`), one-command installer (`setup.sh`)
