#bberg.py

#pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple blpapi
from contextlib import contextmanager
import pandas as pd
from xbbg import blp
import logging


def download_bloomberg(ticker_dict: dict, start_date) -> pd.DataFrame:
    start_date
    all_data = []

    for ticker, name in ticker_dict.items():
        try:
            logging.info(f"Downloading: {ticker} ({name})")
            df = blp.bdh(
                tickers=ticker,
                flds="PX_LAST",
                start_date=start_date,
        #        end_date=END_DATE,
                Per="D"
            )
            df = df.reset_index()
            df.columns = ["Date", "Value"]
            df["Ticker"] = ticker
            df["Name"] = name
            all_data.append(df)
        except Exception as e:
            logging.error(f"Failed to download {ticker}: {e}")

    if not all_data:
        return pd.DataFrame(columns=["Date", "Ticker", "PADD", "Crude_Run"])

    result = pd.concat(all_data, ignore_index=True)
    result["Date"] = pd.to_datetime(result["Date"])
    result = result.rename(columns={"Date": "DATE", "Name": "REGION", "Value": "VALUE"})
    return result[["DATE", "Ticker", "REGION", "VALUE"]].sort_values(["REGION", "DATE"])
