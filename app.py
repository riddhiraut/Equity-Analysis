# Multi-Asset Equity Analytics Dashboard
# Interactive web interface for the DuckDB SQL analytics engine

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


# 1) UNIVERSE DEF

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
st.title("Multi‑Asset Equity Analytics")

# user controls
with st.sidebar:
    st.header("⚙️\u2003Controls")

    selected_tickers = st.multiselect(
        "Select Assets",
        options=TICKERS,
        default=TICKERS
    )

    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-01-01"))
    end_date = st.date_input("End Date", value=pd.to_datetime("today"))

    ma_short = st.slider("Short MA Window (days)", 5, 50, 20)
    ma_long = st.slider("Long MA Window (days)", 20, 200, 50)
    vol_window = st.slider("Volatility Window (days)", 10, 60, 21)

    if st.button("🔄\u2003Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# 3) DATA LOADING (cached)

@st.cache_data
def load_data_cached(tickers, start, end):
    try:
        raw = yf.download(tickers, start=start, end=end, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            df = raw["Close"].copy() if "Close" in raw.columns.levels[0] else raw.xs("Close", axis=1, level=0)
        elif "Close" in raw.columns:
            df = raw[["Close"]].copy() if isinstance(raw["Close"], pd.Series) else raw["Close"].copy()
        else:
            df = raw.copy()

        if isinstance(df, pd.Series):
            df = df.to_frame()

        df = df.reset_index()
        long = df.melt(id_vars="Date", var_name="ticker", value_name="close")
        long = long.dropna(subset=["close"])
        long = long.rename(columns={"Date": "date"})
        long["date"] = pd.to_datetime(long["date"]).dt.date
        return long
    except Exception as e:
        st.error(f"🚨\u2003Data download failed: {e}")
        st.stop()

def load_data(tickers, start, end):
    df = load_data_cached(tickers, start, end)
    
    con = duckdb.connect()
    con.register("prices_raw", df)
    
    con.execute("""
        CREATE OR REPLACE TABLE prices AS
        SELECT ticker, date, close
        FROM prices_raw
        ORDER BY ticker, date
    """)
    
    compute_returns(con)
    return con

if not selected_tickers:
    st.warning("Please select at least one asset from the sidebar.")
    st.stop()

con = load_data(selected_tickers, start_date, end_date)

# compute all metrics
growth_df = compute_cumulative_growth(con)
vol_df = compute_rolling_volatility(con, vol_window)
dd_df = compute_drawdowns(con)
maxdd_df = compute_max_drawdown(con)
rank_df = compute_risk_ranking(con)
sector_df = compute_sector_stats(con, UNIVERSE)
corr_mat = compute_correlation(con, selected_tickers)


# 4) TABS

st.markdown("""
    <style>
    /* adding pipe separator between tabs */
    button[data-baseweb="tab"]:not(:last-child)::after {
        content: "|";
        margin-left: 1.5rem;
        color: #6c757d; /* themed colors */
        font-weight: 300;
    }
    </style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌱\u2003Growth & Trends",
    "💹\u2003Volatility & Drawdown",
    "⛳️\u2003Risk‑Adjusted Rankings",
    "🧩\u2003Sector Summary",
    "🔋\u2003Correlation"
])

# growth & trends
with tab1:
    st.subheader("Cumulative Growth of $1")
    growth_pivot = growth_df.pivot(index="date", columns="ticker", values="growth")
    valid_cols = [t for t in selected_tickers if t in growth_pivot.columns]
    st.line_chart(growth_pivot[valid_cols] if valid_cols else growth_pivot)

    st.subheader("Moving Averages & Regime Signal")
    ticker_ma = st.selectbox("Select ticker for MA plot", valid_cols if valid_cols else selected_tickers, key="ma_ticker")
    
    if ticker_ma:
        ma_df = compute_moving_averages(con, ticker_ma, ma_short, ma_long)

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(ma_df["date"], ma_df["px"], label="Price", linewidth=1.5)
        ax.plot(ma_df["date"], ma_df["sma20"], label=f"SMA{ma_short}", linestyle="--")
        ax.plot(ma_df["date"], ma_df["sma50"], label=f"SMA{ma_long}", linestyle="--")

        for i in range(len(ma_df) - 1):
            color = "green" if ma_df.iloc[i]["regime"] == "bullish" else "red"
            ax.axvspan(ma_df.iloc[i]["date"], ma_df.iloc[i+1]["date"], alpha=0.1, color=color)

        ax.legend()
        ax.set_title(f"{ticker_ma} – Price, Moving Averages & Regime")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

# volatility & drawdown
with tab2:
    st.subheader("Rolling Annualised Volatility")
    vol_pivot = vol_df.pivot(index="date", columns="ticker", values="vol_21d")
    v_cols = [t for t in selected_tickers if t in vol_pivot.columns]
    st.line_chart(vol_pivot[v_cols] if v_cols else vol_pivot)

    st.subheader("Drawdown from Running Peak")
    dd_pivot = dd_df.pivot(index="date", columns="ticker", values="drawdown")
    d_cols = [t for t in selected_tickers if t in dd_pivot.columns]
    st.area_chart(dd_pivot[d_cols] if d_cols else dd_pivot)

    st.subheader("Maximum Drawdown per Asset")
    st.dataframe(maxdd_df, use_container_width=True)

# risk-adjusted rankings
with tab3:
    st.subheader("Risk‑Adjusted Leaderboard")
    st.dataframe(rank_df, use_container_width=True)

    if not rank_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.barplot(data=rank_df, x="ticker", y="sharpe", palette="viridis", ax=ax)
        ax.axhline(0, color="black", linestyle="--", alpha=0.5)
        ax.set_title("Sharpe Ratio by Asset")
        st.pyplot(fig)

# sector summary
with tab4:
    st.subheader("Sector Performance Summary")
    st.dataframe(sector_df, use_container_width=True)

    if not sector_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.barplot(data=sector_df, x="sector", y="avg_ann_return", palette="coolwarm", ax=ax)
        ax.set_title("Average Annual Return by Sector")
        ax.tick_params(axis='x', rotation=45)
        st.pyplot(fig)

# correlation
with tab5:
    st.subheader("Return Correlation Matrix")
    if corr_mat.empty or corr_mat.shape[0] < 2:
        st.warning("Select at least two tickers to display correlation.")
    else:
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(
            corr_mat,
            annot=True,
            fmt='.2f',
            cmap="RdYlBu_r",
            vmin=-0.2,
            vmax=1.0,
            square=True,
            ax=ax
        )
        ax.set_title("Pairwise Return Correlations")
        st.pyplot(fig)
