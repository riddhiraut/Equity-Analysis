import duckdb
import pandas as pd
import yfinance as yf


# 0) SETUP

def load_and_register_data(tickers, start, end):
    """
    Download price data from Yahoo Finance, reshape to long format,
    and register it as a DuckDB table.
    """
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True)
    if "Close" in raw:
        raw = raw["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(name=tickers[0] if isinstance(tickers, list) else tickers)

    raw = raw.reset_index()
    long = raw.melt(id_vars="Date", var_name="ticker", value_name="close")
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


# 1) DAILY RETURNS (LAG)

def compute_returns(con):
    """
    Calculate daily returns using window LAG function and handle initial nulls.
    """
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


# 2) MOVING AVGS AND TREND REGIME SIGNAL (windowed frames)

def compute_moving_averages(con, ticker, ma_short=20, ma_long=50):
    """
    Calculate short- and long-term simple moving averages using window functions.
    """
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
    """, [ma_short, ma_long, ticker]).df()


# 3) CUMULATIVE RETURN, GROWTH OF $1 (log-return compounding)

def compute_cumulative_growth(con):
    """
    Compute cumulative growth of $1 per ticker using log-return compounding.
    """
    return con.execute("""
        SELECT
            ticker, date,
            EXP(SUM(LN(1 + daily_return)) OVER (PARTITION BY ticker ORDER BY date)) AS growth
        FROM returns
        ORDER BY date, ticker
    """).df()


# 4) ROLLING ANN. VOLATILITY (windowed STDDEV_SAMP)

def compute_rolling_volatility(con, window=21):
    """
    Calculate rolling annualised volatility using sample standard deviation.
    """
    return con.execute("""
        SELECT
            ticker, date,
            STDDEV_SAMP(daily_return) OVER (PARTITION BY ticker ORDER BY date
                ROWS BETWEEN ? PRECEDING AND CURRENT ROW) * SQRT(252) AS vol_21d
        FROM returns
    """, [window]).df()


# 5) DRAWDOWN + MAX DRAWDOWN (running peak)

def compute_drawdowns(con):
    """
    Calculate daily percentage drawdown relative to the running peak price.
    """
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
    """
    Aggregate maximum drawdown per ticker.
    """
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


# 6) RISK ADJUSTED LEADERBOARD (RANK)

def compute_risk_ranking(con):
    """
    Compute annualised return, annualised volatility, and Sharpe ratio.
    """
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


# 7) SECTOR PERFORMANCE (GROUP BY aggregation)

def compute_sector_stats(con, sector_map):
    """
    Aggregate performance metrics by sector.
    """
    con.execute("ALTER TABLE prices ADD COLUMN IF NOT EXISTS sector VARCHAR")
    con.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS sector VARCHAR")
    for ticker, sector in sector_map.items():
        con.execute(f"UPDATE prices SET sector = '{sector}' WHERE ticker = '{ticker}'")
        con.execute(f"UPDATE returns SET sector = '{sector}' WHERE ticker = '{ticker}'")

    return con.execute("""
        SELECT
            sector,
            COUNT(DISTINCT ticker) AS n_names,
            ROUND(AVG(daily_return) * 252, 3) AS avg_ann_return,
            ROUND(STDDEV_SAMP(daily_return) * SQRT(252), 3) AS avg_ann_vol
        FROM returns
        GROUP BY sector
        ORDER BY avg_ann_return DESC
    """).df()


# 8) CORR MATRIX (self-join + CORR)

def compute_correlation(con, tickers):
    """
    Build a pairwise correlation matrix for daily returns.
    """
    corr_long = con.execute("""
        SELECT a.ticker AS t1, b.ticker AS t2, CORR(a.daily_return, b.daily_return) AS corr
        FROM returns a
        JOIN returns b ON a.date = b.date
        GROUP BY a.ticker, b.ticker
    """).df()

    cmat = corr_long.pivot(index="t1", columns="t2", values="corr")
    cmat = cmat.reindex(index=tickers, columns=tickers)
    return cmat
