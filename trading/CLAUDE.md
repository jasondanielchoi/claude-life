# Trading Context

## Goal
Trade successfully in the stock market. Focus on finding edge, managing risk, and systematic execution.

## Strategy (fill in)
- Style: [ ] Day trade / [ ] Swing / [ ] Position / [ ] Options
- Primary instruments:
- Timeframes:
- Edge hypothesis:

## Risk Rules (fill in)
- Max position size:
- Max daily loss:
- Stop loss approach:

## Watchlist (fill in)
- Tickers:

## Data Sources
- `yfinance` — free OHLCV, options chain, fundamentals
- `fetch` MCP — pull earnings, news, SEC filings
- `brave-search` MCP — macro news, sector sentiment

## Tracking
- Trade log: `data/trades.db` (SQLite)
- Schema: date, ticker, direction, entry, exit, size, pnl, notes
