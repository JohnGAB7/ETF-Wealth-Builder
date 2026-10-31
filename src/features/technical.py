import numpy as np
import pandas as pd

def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def build_technical_features(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty or "Close" not in history:
        return pd.DataFrame()
    close = history["Close"].astype(float)
    returns = close.pct_change()
    rolling_max = close.cummax()
    out = pd.DataFrame(index=history.index)
    out["return_1d"] = returns
    out["momentum_21d"] = close.pct_change(21)
    out["momentum_63d"] = close.pct_change(63)
    out["momentum_126d"] = close.pct_change(126)
    out["drawdown"] = close / rolling_max - 1
    out["ma50_gap"] = close / close.rolling(50).mean() - 1
    out["ma200_gap"] = close / close.rolling(200).mean() - 1
    out["rsi14"] = rsi(close)
    out["realized_vol_21d"] = returns.rolling(21).std() * np.sqrt(252)
    out["realized_vol_63d"] = returns.rolling(63).std() * np.sqrt(252)
    return out.replace([np.inf, -np.inf], np.nan)
