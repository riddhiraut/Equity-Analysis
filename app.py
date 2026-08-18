import streamlit as st
import duckdb
import yfinance as yf

st.title("Multi-Asset Equity Analytics")

# user controls
ticker = st.selectbox("Select Asset", ["AAPL", "MSFT", "NVDA", "JPM"])
days = st.slider("Select Days of History", 30, 365, 180)

# fetch data
df = yf.download(ticker, period=f"{days}d", auto_adjust=True)

# flatten multiindex columns so duckdb can read 'Close' properly
if isinstance(df.columns, pd.MultiIndex):
    df = df["Close"].reset_index()
    df.columns = ["Date", "Close"]
else:
    df = df[["Close"]].reset_index()

# duckdb sql uery
con = duckdb.connect()
con.register("prices", df)

query = """
    SELECT 
        Date, 
        Close,
        AVG(Close) OVER (ORDER BY Date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS MA_20
    FROM prices
"""
result = con.execute(query).df()

# visuals
st.line_chart(result.set_index("Date")[["Close", "MA_20"]])
st.dataframe(result.tail(10))
