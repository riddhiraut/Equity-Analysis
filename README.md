# Quantitative Equity & Index Analytics Engine

A multi-asset equity analytics suite that processes, models, and visualizes market performance and risk metrics. Powered by **DuckDB SQL** for core quantitative execution, the project is accessible via an interactive web application or a standalone analytical notebook.

---

## Interactive Web Application (`app.py`)

A user-facing dashboard built with **Streamlit** that executes dynamic DuckDB SQL queries over real-time market data fetched via `yfinance`.

### Features & Capabilities
* **Dynamic Querying:** Change parameters like stock tickers and window historical lookbacks on the fly.
* **On-the-Fly SQL Execution:** Calculates moving averages and trend windows dynamically via DuckDB.
* **Interactive Visualizations:** Interactive time-series price and trend overlays alongside structured raw tabular outputs.

---

## SQL Analytics Engine (`notebook.ipynb`)

A compact quantitative analysis engine running entirely in **SQL (DuckDB)** inside a single notebook environment. Python is used purely to import raw price data and plot charts directly over SQL query results.

The engine answers core quantitative market questions: historical asset performance, volatility, trend regime flips, drawdown depths, risk-adjusted performance rankings, and asset correlations.

### SQL Techniques Demonstrated
Every metric is computed directly through SQL queries:
1. **Daily Returns:** Calculated via the `LAG` window function.
2. **Moving Averages & Trend Regimes:** Built with explicit window frames (`ROWS BETWEEN ... PRECEDING`).
3. **Cumulative Compounding:** Growth of $1 tracked via log returns (`EXP(SUM(LN(1 + r)))`).
4. **Rolling Annualized Volatility:** Computed using windowed `STDDEV_SAMP`.
5. **Drawdowns & Max Drawdown:** Computed from a running peak using `MAX() OVER (ROWS UNBOUNDED PRECEDING)`.
6. **Risk-Adjusted Leaderboard:** Ranks assets by a simplified Sharpe ratio using `RANK()`.
7. **Sector Performance Rollups:** Aggregated using grouped CTEs and `GROUP BY`.
8. **Return Correlation Matrix:** Built using self-joins and the `CORR` statistical aggregate.

Together, these patterns demonstrate key analytics concepts including CTEs, window functions, running aggregates, ranking, joins, and statistical functions.

---

## Possible Extensions

* Deploy basic version of notebook as a web app (DONE, UPDATED)
* Add a benchmark (e.g., SPY) to compute Jensen's Alpha and Beta per asset
* Convert the SQL trend regime signal into an automated backtested trading strategy
* Allow user-defined portfolio weights for basket-level risk calculation
