# Multi-Asset Equity Analytics with SQL

A compact analytics engine that computes performance and risk metrics for a basket of equities entirely in **SQL (DuckDB)**, running in a single Google Colab notebook. Python is used only to load data and draw charts on top of the SQL output.

The goal is to answer the questions a markets or analytics team actually asks: how has each name performed, how risky is it, when did the trend flip, how deep were the drawdowns, which names lead on a risk-adjusted basis, and how correlated is everything.

## SQL techniques demonstrated

Every metric below is computed in a SQL query:
1. **Daily returns** using the `LAG` window function
2. **Moving averages and a trend regime signal** with explicit window frames (`ROWS BETWEEN ... PRECEDING`)
3. **Cumulative compounding** (growth of one dollar) via log returns, `EXP(SUM(LN(1 + r)))`
4. **Rolling annualized volatility** using windowed `STDDEV_SAMP`
5. **Drawdown and max drawdown** from a running peak (`MAX ... UNBOUNDED PRECEDING`)
6. **Risk-adjusted leaderboard** ranking names by a simplified Sharpe ratio with `RANK()`
7. **Sector performance rollups** with `GROUP BY` aggregation
8. **Return correlation matrix** via a self-join and the `CORR` aggregate

Together these cover the CTE, window function, running aggregate, ranking, join, and statistical aggregate patterns that analyst and analytics roles screen for.

## Data

The notebook pulls real daily prices from Yahoo Finance (via `yfinance`) when run in Colab. If that call fails for any reason (offline, rate limit, API change), it falls back to a reproducible simulated dataset built from a market plus sector plus idiosyncratic factor model, so within-sector names stay more correlated than cross-sector ones. Either path produces the same schema, so the notebook always runs end to end.

Universe: 12 large-cap names across Technology, Financials, Energy, Consumer Staples, and Health Care.

## Possible future extensions

- Adding a benchmark (for example SPY) and compute beta and alpha per name
- Turning the regime signal into a simple long-short strategy and backtest its cumulative return
- Parameterizing the universe to accept any ticker list
