# Multi-Asset Equity Analytics Dashboard
# Interactive web interface for the DuckDB SQL analytics engine.
# User controls: ticker selection, date range, window sizes.
# Visualisations: growth curves, volatility, drawdowns, leaderboard, sector stats, correlation.


# 0) BASIC

import yfinance as yf
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import duckdb
from queries import (
    load_and_register_data,
    compute_returns,
    compute_moving_averages,
    compute_cumulative_growth,
    compute_rolling_volatility,
    compute_drawdowns,
    compute_max_drawdown,
    compute_risk_ranking,
    compute_sector_stats,
    compute_correlation,
)


# 1) UNIVERSE DEF (hardcoded sector map as in notebook)

UNIVERSE = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "JPM": "Financials", "GS": "Financials", "BAC": "Financials",
    "XOM": "Energy", "CVX": "Energy",
    "KO": "Consumer Staples", "PG": "Consumer Staples",
    "JNJ": "Health Care", "PFE": "Health Care",
}
TICKERS = list(UNIVERSE.keys())

# 2) STREAMLIT CONFIG

st.set_page_config(layout="wide")
st.title("📈 Multi‑Asset Equity Analytics Dashboard")

# user controls
with st.sidebar:
    st.header("⚙️ Controls")

    # asset selection (multi-select)
    selected_tickers = st.multiselect(
        "Select Assets",
        options=TICKERS,
        default=["AAPL", "MSFT", "NVDA", "JPM"]  # default subset from the original app
    )

    # date range
    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-01-01"))
    end_date = st.date_input("End Date", value=pd.to_datetime("today"))

    # moving average windows
    ma_short = st.slider("Short MA Window (days)", 5, 50, 20)
    ma_long = st.slider("Long MA Window (days)", 20, 200, 50)

    # volatility window
    vol_window = st.slider("Volatility Window (days)", 10, 60, 21)

    # refresh / clear cache
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# 3) DATA LOADING (cached)

@st.cache_data
def load_data_cached(tickers, start, end):
    # download and cache the raw price data as a df.
    try:
        # download data from yf
        df = yf.download(tickers, start=start, end=end, auto_adjust=True)["Close"]
        df = df.reset_index()
        # melt to long format
        long = df.melt(id_vars="Date", var_name="ticker", value_name="close")
        long = long.dropna(subset=["close"])
        long = long.rename(columns={"Date": "date"})
        long["date"] = pd.to_datetime(long["date"]).dt.date
        return long
    except Exception as e:
        st.error(f"🚨 Data download failed: {e}")
        st.stop()

def load_data(tickers, start, end):
    # get the cached DataFrame
    df = load_data_cached(tickers, start, end)
    
    # create a fresh duckDB connection (not cached)
    con = duckdb.connect()
    con.register("prices_raw", df)
    
    # create the prices table
    con.execute("""
        CREATE OR REPLACE TABLE prices AS
        SELECT ticker, date, close
        FROM prices_raw
        ORDER BY ticker, date
    """)
    
    # compute returns
    compute_returns(con)
    
    return con

# guard against empty selection
if not selected_tickers:
    st.warning("Please select at least one asset from the sidebar.")
    st.stop()

con = load_data(selected_tickers, start_date, end_date)

# compute all metrics (cached per parameters)
def get_growth(_con):
    return compute_cumulative_growth(_con)
def get_volatility(_con, window):
    return compute_rolling_volatility(_con, window)
def get_drawdowns(_con):
    return compute_drawdowns(_con)
def get_max_drawdown(_con):
    return compute_max_drawdown(_con)
def get_ranking(_con):
    return compute_risk_ranking(_con)
def get_sector_stats(_con, sector_map):
    return compute_sector_stats(_con, sector_map)
def get_correlation(_con, tickers):
    return compute_correlation(_con, tickers)

# fetch all dataframes
growth_df = get_growth(con)
vol_df = get_volatility(con, vol_window)
dd_df = get_drawdowns(con)
maxdd_df = get_max_drawdown(con)
rank_df = get_ranking(con)
sector_df = get_sector_stats(con, UNIVERSE)
corr_mat = get_correlation(con, selected_tickers)


# 4) TABS: organise output by theme

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌱 Growth & Trends",
    "💹 Volatility & Drawdown",
    "⛳️ Risk‑Adjusted Rankings",
    "🧩 Sector Summary",
    "🔋 Correlation"
])

# growth & trends (sections 2 & 3 from notebook)
with tab1:
    # cumulative growth
    st.subheader("Cumulative Growth of $1")
    growth_pivot = growth_df.pivot(index="date", columns="ticker", values="growth")
    st.line_chart(growth_pivot[selected_tickers])

    # moving averages + regime signal
    st.subheader("Moving Averages & Regime Signal")
    ticker_ma = st.selectbox("Select ticker for MA plot", selected_tickers, key="ma_ticker")
    ma_df = compute_moving_averages(con, ticker_ma, ma_short, ma_long)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ma_df["date"], ma_df["px"], label="Price", linewidth=1.5)
    ax.plot(ma_df["date"], ma_df["sma20"], label=f"SMA{ma_short}", linestyle="--")
    ax.plot(ma_df["date"], ma_df["sma50"], label=f"SMA{ma_long}", linestyle="--")

    # shade bullish (green) / bearish (red) regimes
    for i in range(len(ma_df) - 1):
        color = "green" if ma_df.iloc[i]["regime"] == "bullish" else "red"
        ax.axvspan(ma_df.iloc[i]["date"], ma_df.iloc[i+1]["date"], alpha=0.1, color=color)

    ax.legend()
    ax.set_title(f"{ticker_ma} – Price, Moving Averages & Regime")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

# volatility & drawdown (sections 4 & 5)
with tab2:
    # rolling volatility
    st.subheader("Rolling Annualised Volatility")
    vol_pivot = vol_df.pivot(index="date", columns="ticker", values="vol_21d")
    st.line_chart(vol_pivot[selected_tickers])

    # drawdown
    st.subheader("Drawdown from Running Peak")
    dd_pivot = dd_df.pivot(index="date", columns="ticker", values="drawdown")
    st.area_chart(dd_pivot[selected_tickers])

    st.subheader("Maximum Drawdown per Asset")
    st.dataframe(maxdd_df, use_container_width=True)

# risk-adjusted rankings (section 6)
with tab3:
    st.subheader("Risk‑Adjusted Leaderboard")
    st.dataframe(rank_df, use_container_width=True)

    # sharpe ratio bar chart
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=rank_df, x="ticker", y="sharpe", palette="viridis", ax=ax)
    ax.axhline(0, color="black", linestyle="--", alpha=0.5)
    ax.set_title("Sharpe Ratio by Asset")
    st.pyplot(fig)

# sector summary (section 7)
with tab4:
    st.subheader("Sector Performance Summary")
    st.dataframe(sector_df, use_container_width=True)

    # avg annual return by sector
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=sector_df, x="sector", y="avg_ann_return", palette="coolwarm", ax=ax)
    ax.set_title("Average Annual Return by Sector")
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

# correlation (section 8)
with tab5:
    st.subheader("Return Correlation Matrix")
    if corr_mat.empty or corr_mat.shape[0] < 2:
        st.warning("Select at least two tickers to display correlation.")
    else:
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(
            corr_mat,
            annot=True,
            cmap="RdYlBu_r",
            vmin=-0.2,
            vmax=1.0,
            square=True,
            ax=ax
        )
        ax.set_title("Pairwise Return Correlations")
        st.pyplot(fig)
