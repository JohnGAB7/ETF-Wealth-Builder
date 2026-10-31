import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingRegressor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

FEATURES = [
    "momentum_21d", "momentum_63d", "momentum_126d", "drawdown",
    "ma50_gap", "ma200_gap", "rsi14", "realized_vol_21d", "realized_vol_63d",
]

def make_training_frame(features: pd.DataFrame, close: pd.Series, horizon: int = 63) -> pd.DataFrame:
    frame = features.copy()
    frame["forward_return"] = close.shift(-horizon) / close - 1
    frame["positive_forward_return"] = np.where(
        frame["forward_return"].notna(),
        (frame["forward_return"] > 0).astype(float),
        np.nan,
    )
    return frame.replace([np.inf, -np.inf], np.nan)

def fit_predict(frame: pd.DataFrame, min_rows: int = 500) -> dict:
    """Chronological holdout and time-series calibration.

    This is a baseline research model, not yet a fully purged/embargoed nested
    walk-forward engine. Overlapping horizon labels can still make validation
    optimistic; see docs/MODEL_GOVERNANCE.md before using signals with real money.
    """
    cols = [c for c in FEATURES if c in frame.columns]
    data = frame.dropna(subset=cols + ["forward_return", "positive_forward_return"]).copy()
    if len(data) < min_rows:
        return {"status": "INSUFFICIENT_EVIDENCE", "rows": len(data)}
    split = int(len(data) * 0.75)
    train, test = data.iloc[:split], data.iloc[split:]
    if len(test) < 50 or train["positive_forward_return"].nunique() < 2:
        return {"status": "INSUFFICIENT_EVIDENCE", "rows": len(data)}
    base = RandomForestClassifier(
        n_estimators=250, max_depth=5, min_samples_leaf=15,
        class_weight="balanced_subsample", random_state=42, n_jobs=-1,
    )
    cv = TimeSeriesSplit(n_splits=3)
    model = CalibratedClassifierCV(base, method="sigmoid", cv=cv)
    model.fit(train[cols], train["positive_forward_return"].astype(int))
    proba = model.predict_proba(test[cols])[:, 1]
    y = test["positive_forward_return"].astype(int).values
    metrics = {"brier": float(brier_score_loss(y, proba))}
    if len(np.unique(y)) == 2:
        metrics["auc"] = float(roc_auc_score(y, proba))

    # Final fit for latest inference; historical validation metrics remain held out.
    model.fit(data[cols], data["positive_forward_return"].astype(int))
    latest = frame.dropna(subset=cols).iloc[[-1]][cols]
    p_positive = float(model.predict_proba(latest)[0, 1])
    reg = HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=10,
                                        l2_regularization=2, random_state=42)
    reg.fit(train[cols], train["forward_return"])
    expected_return = float(reg.predict(latest)[0])
    return {
        "status": "MODEL_ESTIMATE",
        "prob_positive": p_positive,
        "expected_return": expected_return,
        "validation": metrics,
        "rows": len(data),
        "model": "TimeSeriesCalibratedRandomForest + HistGradientBoostingRegressor",
    }
