# **Quantitative Equity Analytics Engine (Live | WIP 🏗️)**

A lightweight multi-asset equity engine and interactive dashboard powered by Python embedded DuckDB SQL :) See Roadmap below for future additions

---

**Current Status**

Notebook: Test environment for prototyping.

WebApp: Live, deployed multi-asset Streamlit UI executing DuckDB SQL analytics (including cumulative growth, moving-average regime signals, rolling volatility, drawdown analysis, risk-adjusted rankings, sector performance, and return correlations) on live Yahoo Finance data.

---

**Roadmap**

Notebook:
- [x] Build core Python/DuckDB analytics engine for multi-asset equity analysis
- [ ] Add SPY benchmark to calculate Jensen's Alpha and Beta
- [ ] Implement an automated backtest for the SQL trend-regime signal

WebApp:
- [x] Deploy initial Streamlit dynamic querying interface
- [x] Port notebook's SQL engine to the web dashboard
- [ ] Add custom portfolio weighting for basket-level risk calculation
