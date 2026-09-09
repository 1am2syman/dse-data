# Data Dictionary — dse-data

Every field the skill can return, its meaning, units, and **DSE-specific coverage**
(measured 2026-09 over all ~350 listed symbols). `null` always means *absent upstream*
— not an error.

## Snapshot — core fields (default)

| field | meaning | unit / notes | DSE coverage |
|---|---|---|---|
| `ticker` | TradingView symbol | bare code, e.g. `GP` (exchange prefix `DSEBD:` added in history) | 350/350 |
| `description` | company name | string | 350/350 |
| `close` | last traded price | BDT | 350/350 |
| `open` `high` `low` | session OHLC | BDT | 350/350 |
| `change` | day change | % vs yesterday's close | 350/350 |
| `change_abs` | day change | BDT | 350/350 |
| `volume` | shares traded today | count | 350/350 |
| `average_volume_10d_calc` | 10-day average volume | count | 350/350 |
| `relative_volume_10d_calc` | today's volume ÷ 10-day average | × (1.0 = normal) | 350/350 |
| `gap` | open vs yesterday close | % | 350/350 |
| `change_from_open` | close vs open | % (intraday direction) | 350/350 |
| `market_cap_basic` | market capitalization | BDT | 323/350 |
| `price_earnings_ttm` | P/E, trailing 12 months | ratio; null = loss-making/insufficient data | 169/350 |
| `sector` `industry` | TradingView classification | string | 350/350 |
| `RSI` | RSI-14 | 0–100 (<30 oversold, >70 overbought) | 350/350 |
| `SMA50` `SMA200` | simple moving averages | BDT | 350/350 |
| `Recommend.All` | TradingView composite rating | −1 (sell) … +1 (buy) | 350/350 |
| `price_52_week_high` `price_52_week_low` | 52-week band | BDT | 350/350 |
| `Perf.W` `Perf.1M` `Perf.YTD` | performance windows | % | 350/350 |

## Snapshot — `--full` additions

Technicals (350/350): `MACD.macd`, `MACD.signal` (MACD above signal = rising momentum),
`Stoch.K` `Stoch.D` (<20 / >80 stretched), `ADX` (<20 no trend → range-friendly; >30
trending), `ATR` (avg true range, BDT), `Mom` (momentum), `W.R` (Williams %R),
`BB.upper` `BB.lower` (Bollinger 20,2), `EMA10` `EMA20` `EMA50`, `SMA10` `SMA20`,
`Recommend.MA` `Recommend.Other` (rating split: moving averages / oscillators),
`Volatility.D` (daily volatility %).

Fundamentals (partial for DSE): `dividends_yield_current` 323/350 ·
`total_shares_outstanding_fundamental` 295/350 · `price_book_ratio` 258/350 ·
`current_ratio` 252/350 · `number_of_employees` 237/350 ·
`earnings_per_share_basic_ttm` / `total_revenue_ttm` / `net_income_ttm` 232/350 ·
`price_free_cash_flow_ttm` 132/350. **Never provided for DSE:** beta, debt-to-asset.

## history bars

| field | meaning |
|---|---|
| `datetime` | bar start, ISO 8601 UTC (session 10:00 BST → `04:00Z`) |
| `open` `high` `low` `close` | BDT, **split-adjusted** (bonus/split events restated) |
| `volume` | shares; `null` possible |

Interval map: `1m 5m 15m 30m 1h 2h 4h 1D 1W 1M`. Depth: ~5,000 bars per request
(≈20 sessions of 5-min, years of daily). Intervals `1m 5m 15m 1h` correspond to
"1m 5m 15m 1h" in helper `--period` shorthand? No — helpers' `--period` selects a
**lookback length** (see below), not a bar size.

## Helper period shorthand (`price.py --period`)

`1w`→5 bars · `2w`→10 · `1m`→21 · `3m`→63 · `6m`→126 · `1y`→252 · `2y`→504 ·
`3y`→756 · `5y`→1260 · `max`→1200 (trading days at 1D; intraday intervals need
proportionally more bars — pass `--bars` directly for intraday depth).

## index

`DSEX` (broad) and `DSES` (Shariah): `close` (level), `change` (%), `open`, `high`,
`low` — intraday, delayed like everything else.

## semantics notes

- **All data is delayed** (2–15 min typical) — keyless anonymous access.
- **Trading hours:** Sun–Thu 10:00–14:00 BST. Outside hours, snapshot shows the last
  session; "live" fields freeze.
- **Null ≠ zero:** a null P/E means loss-making or insufficient data; a 0 dividend
  yield means none declared.
- Prices are TradingView's split-adjusted series and can be **restated** after
  corporate actions — periodically re-pull history.
