import logging
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

def get_history(symbol: str, period: str = "10y") -> pd.DataFrame:
    """Download adjusted daily history. Empty data is returned on provider failure."""
    try:
        df = yf.download(symbol, period=period, auto_adjust=True, progress=False)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        return df.dropna(subset=["Close"])
    except Exception as exc:
        log.warning("Price download failed for %s: %s", symbol, exc)
        return pd.DataFrame()
