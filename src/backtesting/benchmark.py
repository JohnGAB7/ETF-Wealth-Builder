import pandas as pd

def monthly_dca(close: pd.Series, contribution: float = 500.0) -> pd.DataFrame:
    """Simple monthly DCA benchmark using first available observation per month."""
    prices = close.dropna().resample("MS").first().dropna()
    units, invested, rows = 0.0, 0.0, []
    for dt, price in prices.items():
        units += contribution / float(price)
        invested += contribution
        rows.append({"date": dt, "price": float(price), "units": units,
                     "invested": invested, "portfolio_value": units * float(price)})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
