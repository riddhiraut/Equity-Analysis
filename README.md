# **Quantitative Equity Analytics Engine (WIP 🏗️)**

> A lightweight multi-asset equity engine and interactive dashboard powered by DuckDB SQL and Streamlit :)

---

**Current Status**

Notebook: Multi-asset analytics engine using DuckDB SQL window functions, CTEs, and running aggregates to compute returns, volatility, drawdowns, and asset correlations.

WebApp: Streamlit dashboard executing dynamic queries on live market data for real-time visualization and risk analysis.

---

**Roadmap**

Notebook:
- [x] Build core DuckDB analytics engine for multi-asset equity analysis
- [ ] Add SPY benchmark to calculate Jensen's Alpha and Beta
- [ ] Implement an automated backtest for the SQL trend-regime signal

WebApp:
- [x] Deploy initial Streamlit dynamic querying interface
- [ ] Port full notebook statistical engine to the web dashboard
- [ ] Add custom portfolio weighting for basket-level risk calculation
