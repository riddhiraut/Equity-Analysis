import duckdb
import pandas as pd
import yfinance as yf


# 0) SETUP

def load_and_register_data(tickers, start, end):
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

    con = duckdb.connect()
    con.register("prices_raw", long)

    con.execute("""
        CREATE OR REPLACE TABLE prices AS
        SELECT ticker, date, close
        FROM prices_raw
        ORDER BY ticker, date
    """)
    return con


# 1) DAILY RETURNS

def compute_returns(con):
    con.execute("""
        CREATE OR REPLACE TABLE returns AS
        WITH r AS (
            SELECT
                ticker, date, close,
                close / LAG(close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS daily_return
            FROM prices
        )
        SELECT ticker, date, close, COALESCE(daily_return, 0) AS daily_return
        FROM r
    """)
    return con.execute("SELECT * FROM returns LIMIT 5").df()


# 2) MOVING AVGS AND TREND REGIME SIGNAL

def compute_moving_averages(con, ticker, ma_short=20, ma_long=50):
    return con.execute("""
        WITH ma AS (
            SELECT
                ticker, date, close,
                AVG(close) OVER (PARTITION BY ticker ORDER BY date
                                 ROWS BETWEEN ? PRECEDING AND CURRENT ROW) AS sma20,
                AVG(close) OVER (PARTITION BY ticker ORDER BY date
                                 ROWS BETWEEN ? PRECEDING AND CURRENT ROW) AS sma50
            FROM prices
            WHERE ticker = ?
        )
        SELECT
            ticker, date,
            ROUND(close, 2) AS px,
            ROUND(sma20, 2) AS sma20,
            ROUND(sma50, 2) AS sma50,
            CASE WHEN sma20 > sma50 THEN 'bullish' ELSE 'bearish' END AS regime
        FROM ma
        ORDER BY date
    """, [ma_short - 1, ma_long - 1, ticker]).df()


# 3) CUMULATIVE RETURN

def compute_cumulative_growth(con):
    return con.execute("""
        SELECT
            ticker, date,
            EXP(SUM(LN(1 + daily_return)) OVER (PARTITION BY ticker ORDER BY date)) AS growth
        FROM returns
        ORDER BY date, ticker
    """).df()


# 4) ROLLING ANN. VOLATILITY

def compute_rolling_volatility(con, window=21):
    return con.execute("""
        SELECT
            ticker, date,
            STDDEV_SAMP(daily_return) OVER (PARTITION BY ticker ORDER BY date
                ROWS BETWEEN ? PRECEDING AND CURRENT ROW) * SQRT(252) AS vol_21d
        FROM returns
    """, [window - 1]).df()


# 5) DRAWDOWN + MAX DRAWDOWN

def compute_drawdowns(con):
    return con.execute("""
        WITH dd AS (
            SELECT
                ticker, date, close,
                MAX(close) OVER (PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_peak
            FROM prices
        )
        SELECT ticker, date, close / running_peak - 1 AS drawdown
        FROM dd
    """).df()


def compute_max_drawdown(con):
    return con.execute("""
        WITH dd AS (
            SELECT
                ticker, date, close,
                MAX(close) OVER (PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_peak
            FROM prices
        )
        SELECT ticker, ROUND(MIN(close / running_peak - 1), 4) AS max_drawdown
        FROM dd
        GROUP BY ticker
        ORDER BY max_drawdown
    """).df()


# 6) RISK ADJUSTED LEADERBOARD

def compute_risk_ranking(con):
    return con.execute("""
        WITH stats AS (
            SELECT
                ticker,
                AVG(daily_return) * 252 AS ann_return,
                STDDEV_SAMP(daily_return) * SQRT(252) AS ann_vol,
                AVG(daily_return) / NULLIF(STDDEV_SAMP(daily_return), 0) * SQRT(252) AS sharpe
            FROM returns
            GROUP BY ticker
        )
        SELECT
            RANK() OVER (ORDER BY sharpe DESC) AS rank,
            ticker,
            ROUND(ann_return, 3) AS ann_return,
            ROUND(ann_vol, 3) AS ann_vol,
            ROUND(sharpe, 2) AS sharpe
        FROM stats
        ORDER BY sharpe DESC
    """).df()


# 7) SECTOR PERFORMANCE

def compute_sector_stats(con, sector_map):
    sector_df = pd.DataFrame(list(sector_map.items()), columns=["ticker", "sector"])
    con.register("sector_map_df", sector_df)
    return con.execute("""
        SELECT
            s.sector,
            COUNT(DISTINCT r.ticker) AS n_names,
            ROUND(AVG(r.daily_return) * 252, 3) AS avg_ann_return,
            ROUND(STDDEV_SAMP(r.daily_return) * SQRT(252), 3) AS avg_ann_vol
        FROM returns r
        JOIN sector_map_df s ON r.ticker = s.ticker
        GROUP BY s.sector
        ORDER BY avg_ann_return DESC
    """).df()


# 8) CORR MATRIX

def compute_correlation(con, tickers):
    corr_long = con.execute("""
        SELECT a.ticker AS t1, b.ticker AS t2, CORR(a.daily_return, b.daily_return) AS corr
        FROM returns a
        JOIN returns b ON a.date = b.date
        GROUP BY a.ticker, b.ticker
    """).df()

    if corr_long.empty:
        return pd.DataFrame()

    cmat = corr_long.pivot(index="t1", columns="t2", values="corr")
    valid_tickers = [t for t in tickers if t in cmat.columns]
    cmat = cmat.reindex(index=valid_tickers, columns=valid_tickers)
    return cmat
