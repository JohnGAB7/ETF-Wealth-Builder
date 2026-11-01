"""Purged walk-forward validation, in OBSERVATION mode (lot 5.1).

What this module does
---------------------
It re-evaluates the existing probabilistic model out of sample, without changing
it, and compares it with two references:

- climatology: the frequency of positive forward returns in each training window,
  used as a constant forecast (reference of the Brier Skill Score);
- a standardised L2 logistic regression on the same features.

Protocol (see docs/audit/LOT5_REPONSE_REVUE_CHATGPT.md, section 3):

- expanding training window, successive test blocks of `test_block` sessions;
- PURGE: a training row t is kept only if its label window (t, t+h] ends before
  the test block starts, i.e. t <= t0 - h - 1. No training label uses a test price;
- the model's internal calibration folds are purged the same way (`h` rows are
  dropped between the inner fit part and the inner calibration part);
- with an expanding window the training set never contains data posterior to
  the test block, so no extra embargo is needed for the outer loop.

Dependence of overlapping labels: a block of n rows with a horizon h holds about
n / h disjoint label windows. `n_eff` reports that number; the confidence
interval of the BSS uses a moving-block bootstrap with blocks of length h, and a
Diebold-Mariano statistic with a Newey-West variance (h - 1 lags) is reported.

Observation mode: `proposed_status` is computed and reported, but nothing in the
signal logic reads it. The gate values come from `validation_gate_proposed` in
config/strategy.yaml and are pending a human decision.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.models.probabilistic import FEATURES

PROB_CLIP = 1e-3
VALIDATED = "VALIDATED"
NOT_VALIDATED = "NOT_VALIDATED"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

DEFAULT_GATE = {
    "min_effective_windows": 20,
    "bss_ci_lower_above": 0.0,
    "min_positive_block_share": 0.60,
    "max_brier_excess_vs_logistic": 0.005,
    "calibration_slope_min": 0.5,
    "calibration_slope_max": 1.5,
}


# ------------------------------------------------------------------ splits

def purged_walk_forward_splits(n_rows: int, horizon: int, min_train: int,
                               test_block: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window splits; training rows whose label overlaps the test are purged."""
    splits = []
    start = min_train + horizon
    while start < n_rows:
        stop = min(start + test_block, n_rows)
        train = np.arange(0, start - horizon)
        test = np.arange(start, stop)
        if len(train) >= min_train and len(test) > 0:
            splits.append((train, test))
        start = stop
    return splits


def purged_inner_splits(n_rows: int, horizon: int, n_splits: int = 3,
                        min_fit: int = 100) -> list[tuple[np.ndarray, np.ndarray]]:
    """Inner calibration folds, purged like the outer loop (h rows dropped)."""
    fold = n_rows // (n_splits + 1)
    splits = []
    for k in range(1, n_splits + 1):
        cal_start = k * fold
        cal_stop = n_rows if k == n_splits else (k + 1) * fold
        fit = np.arange(0, max(0, cal_start - horizon))
        cal = np.arange(cal_start, cal_stop)
        if len(fit) >= min_fit and len(cal) > 0:
            splits.append((fit, cal))
    return splits


# ------------------------------------------------------------------ models

def current_model_factory(horizon: int):
    """The production classifier, unchanged, with purged internal calibration."""
    def fit(x: pd.DataFrame, y: np.ndarray):
        inner = purged_inner_splits(len(x), horizon)
        base = RandomForestClassifier(
            n_estimators=250, max_depth=5, min_samples_leaf=15,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1,
        )
        if not inner or any(len(np.unique(y[f])) < 2 for f, _ in inner):
            model = base.fit(x, y)
        else:
            model = CalibratedClassifierCV(base, method="sigmoid", cv=inner).fit(x, y)
        return lambda z: model.predict_proba(z)[:, 1]
    return fit


def logistic_factory(horizon: int):
    def fit(x: pd.DataFrame, y: np.ndarray):
        model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
        model.fit(x, y)
        return lambda z: model.predict_proba(z)[:, 1]
    return fit


def _expected_return_mae(train: pd.DataFrame, test: pd.DataFrame, cols) -> tuple[float, float]:
    reg = HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=10,
                                        l2_regularization=2, random_state=42)
    reg.fit(train[cols], train["forward_return"])
    pred = reg.predict(test[cols])
    actual = test["forward_return"].to_numpy()
    constant = float(train["forward_return"].mean())
    return float(np.mean(np.abs(pred - actual))), float(np.mean(np.abs(constant - actual)))


# ----------------------------------------------------------------- metrics

def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    q = np.clip(p, PROB_CLIP, 1 - PROB_CLIP)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def skill(loss_model: float, loss_ref: float) -> float | None:
    return None if loss_ref <= 0 else 1.0 - loss_model / loss_ref


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict]:
    """Quantile bins (equal counts): predictions cluster in a narrow range."""
    if len(y) < bins:
        return []
    order = np.argsort(p, kind="stable")
    rows = []
    for chunk in np.array_split(order, bins):
        if len(chunk) == 0:
            continue
        rows.append({"mean_predicted": float(np.mean(p[chunk])),
                     "observed_rate": float(np.mean(y[chunk])), "rows": int(len(chunk))})
    return rows


def calibration_slope(y: np.ndarray, p: np.ndarray) -> tuple[float | None, float | None]:
    """Slope/intercept of an unpenalised logistic fit of y on logit(p); 1 / 0 is ideal."""
    if len(np.unique(y)) < 2:
        return None, None
    q = np.clip(p, PROB_CLIP, 1 - PROB_CLIP)
    logit = np.log(q / (1 - q)).reshape(-1, 1)
    if np.std(logit) < 1e-9:
        return None, None
    fit = LogisticRegression(C=1e6, max_iter=1000).fit(logit, y)
    return float(fit.coef_[0][0]), float(fit.intercept_[0])


def block_bootstrap_bss(y: np.ndarray, p_model: np.ndarray, p_ref: np.ndarray,
                        block: int, draws: int = 1000, seed: int = 42,
                        level: float = 0.90) -> tuple[float | None, float | None]:
    """Moving-block bootstrap CI of BSS = 1 - Brier_model / Brier_ref."""
    n = len(y)
    if n < 2 * block or block < 1:
        return None, None
    loss_m, loss_r = (p_model - y) ** 2, (p_ref - y) ** 2
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block)
    starts_max = n - block
    values = []
    for _ in range(draws):
        starts = rng.integers(0, starts_max + 1, size=n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        ref = loss_r[idx].mean()
        if ref > 0:
            values.append(1.0 - loss_m[idx].mean() / ref)
    if not values:
        return None, None
    alpha = (1 - level) / 2
    return float(np.quantile(values, alpha)), float(np.quantile(values, 1 - alpha))


def diebold_mariano(y: np.ndarray, p_model: np.ndarray, p_ref: np.ndarray,
                    lags: int) -> tuple[float | None, float | None]:
    """DM statistic on d = loss_ref - loss_model (positive = model better).

    Newey-West (Bartlett) long-run variance with `lags` lags; one-sided p-value
    for H1: the model has a lower expected Brier loss than the reference.
    """
    d = (p_ref - y) ** 2 - (p_model - y) ** 2
    n = len(d)
    if n <= lags + 1:
        return None, None
    centred = d - d.mean()
    variance = float(np.dot(centred, centred) / n)
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        variance += 2 * weight * float(np.dot(centred[lag:], centred[:-lag]) / n)
    if variance <= 0:
        return None, None
    stat = float(d.mean() / math.sqrt(variance / n))
    p_value = 0.5 * math.erfc(stat / math.sqrt(2))
    return stat, float(p_value)


def _regime_bss(oos: pd.DataFrame) -> dict:
    """Descriptive only: two or three stress episodes cannot support a rule."""
    out = {}

    def _bss(mask):
        part = oos[mask]
        if len(part) < 30:
            return None
        return skill(brier(part.y.values, part.p_model.values),
                     brier(part.y.values, part.p_clim.values))

    if "realized_vol_63d" in oos and oos["realized_vol_63d"].notna().sum() >= 90:
        terciles = pd.qcut(oos["realized_vol_63d"], 3, labels=["low", "mid", "high"])
        out["volatility"] = {str(k): _bss(terciles == k) for k in ["low", "mid", "high"]}
    if "drawdown" in oos:
        out["drawdown_over_10pct"] = {"yes": _bss(oos["drawdown"] <= -0.10),
                                      "no": _bss(oos["drawdown"] > -0.10)}
    if "ma200_gap" in oos:
        out["above_ma200"] = {"yes": _bss(oos["ma200_gap"] > 0),
                              "no": _bss(oos["ma200_gap"] <= 0)}
    return out


# ------------------------------------------------------------------- gate

def proposed_status(summary: dict, gate: dict | None = None) -> tuple[str, list[str]]:
    """Status the gate WOULD give. Observation only: not used by any signal."""
    gate = {**DEFAULT_GATE, **(gate or {})}
    if summary.get("status") == INSUFFICIENT_HISTORY:
        return INSUFFICIENT_HISTORY, ["historique insuffisant pour un test hors échantillon"]
    reasons = []
    n_eff = summary.get("n_eff") or 0
    if n_eff < gate["min_effective_windows"]:
        reasons.append(f"n_eff {n_eff:.1f} < {gate['min_effective_windows']}")
    low = summary.get("bss_ci_low")
    if low is None or low <= gate["bss_ci_lower_above"]:
        reasons.append("borne basse de l'IC du BSS non > 0")
    share = summary.get("positive_block_share")
    if share is None or share < gate["min_positive_block_share"]:
        reasons.append("BSS positif dans trop peu de blocs")
    b_model, b_logit = summary.get("brier_model"), summary.get("brier_logistic")
    if b_model is not None and b_logit is not None and \
            b_model > b_logit + gate["max_brier_excess_vs_logistic"]:
        reasons.append("moins bon que la régression logistique")
    slope = summary.get("calibration_slope")
    if slope is None or not (gate["calibration_slope_min"] <= slope <= gate["calibration_slope_max"]):
        reasons.append("pente de calibration hors bornes")
    return (VALIDATED if not reasons else NOT_VALIDATED), reasons


# ------------------------------------------------------------------- main

def walk_forward_validate(frame: pd.DataFrame, horizon: int = 63, min_train: int = 500,
                          test_block: int = 126, model_factory=None, logistic=None,
                          probability_threshold: float | None = None,
                          gate: dict | None = None, bootstrap_draws: int = 1000,
                          with_expected_return: bool = True) -> dict:
    """Out-of-sample evaluation of the current model. Does not change any signal."""
    cols = [c for c in FEATURES if c in frame.columns]
    data = frame.dropna(subset=cols + ["forward_return", "positive_forward_return"])
    splits = purged_walk_forward_splits(len(data), horizon, min_train, test_block)
    base = {"mode": "observation", "horizon_days": horizon, "test_block_days": test_block,
            "purge_rows": horizon, "rows": int(len(data))}
    if not splits:
        summary = {**base, "status": INSUFFICIENT_HISTORY, "blocks": 0}
        summary["proposed_status"], summary["proposed_status_reasons"] = proposed_status(summary, gate)
        return summary

    model_factory = model_factory or current_model_factory(horizon)
    logistic = logistic or logistic_factory(horizon)
    pieces, blocks, mae = [], [], []
    for number, (train_idx, test_idx) in enumerate(splits):
        train, test = data.iloc[train_idx], data.iloc[test_idx]
        y_train = train["positive_forward_return"].astype(int).to_numpy()
        if len(np.unique(y_train)) < 2:
            continue
        y = test["positive_forward_return"].astype(int).to_numpy()
        p_model = model_factory(train[cols], y_train)(test[cols])
        p_logit = logistic(train[cols], y_train)(test[cols])
        p_clim = np.full(len(y), float(y_train.mean()))
        piece = pd.DataFrame({"y": y, "p_model": p_model, "p_logit": p_logit,
                              "p_clim": p_clim, "block": number}, index=test.index)
        for extra in ("realized_vol_63d", "drawdown", "ma200_gap"):
            if extra in test:
                piece[extra] = test[extra].to_numpy()
        pieces.append(piece)
        blocks.append({
            "block": number, "start": str(test.index[0])[:10], "end": str(test.index[-1])[:10],
            "rows": int(len(y)), "train_rows": int(len(train)),
            "base_rate_train": float(y_train.mean()), "observed_rate": float(y.mean()),
            "brier_model": brier(y, p_model), "brier_climatology": brier(y, p_clim),
            "bss": skill(brier(y, p_model), brier(y, p_clim)),
        })
        if with_expected_return:
            mae.append(_expected_return_mae(train, test, cols) + (len(y),))

    if not pieces:
        summary = {**base, "status": INSUFFICIENT_HISTORY, "blocks": 0}
        summary["proposed_status"], summary["proposed_status_reasons"] = proposed_status(summary, gate)
        return summary

    oos = pd.concat(pieces)
    y, pm, pl, pc = (oos[c].to_numpy() for c in ("y", "p_model", "p_logit", "p_clim"))
    b_model, b_logit, b_clim = brier(y, pm), brier(y, pl), brier(y, pc)
    ci_low, ci_high = block_bootstrap_bss(y, pm, pc, block=horizon, draws=bootstrap_draws)
    dm_stat, dm_p = diebold_mariano(y, pm, pc, lags=max(0, horizon - 1))
    slope, intercept = calibration_slope(y, pm)
    block_bss = [b["bss"] for b in blocks if b["bss"] is not None]

    summary = {
        **base, "status": "EVALUATED",
        "oos_start": str(oos.index[0])[:10], "oos_end": str(oos.index[-1])[:10],
        "oos_rows": int(len(oos)), "n_eff": round(len(oos) / horizon, 1), "blocks": len(blocks),
        "base_rate_oos": float(y.mean()),
        "brier_model": b_model, "brier_logistic": b_logit, "brier_climatology": b_clim,
        "bss": skill(b_model, b_clim), "bss_logistic": skill(b_logit, b_clim),
        "bss_ci_low": ci_low, "bss_ci_high": ci_high, "bss_ci_level": 0.90,
        "log_loss_model": log_loss(y, pm), "log_loss_logistic": log_loss(y, pl),
        "log_loss_climatology": log_loss(y, pc),
        "auc_model": float(roc_auc_score(y, pm)) if len(np.unique(y)) == 2 else None,
        "dm_stat": dm_stat, "dm_p_value_one_sided": dm_p,
        "calibration_slope": slope, "calibration_intercept": intercept,
        "calibration_table": calibration_table(y, pm),
        "positive_block_share": (sum(v > 0 for v in block_bss) / len(block_bss)
                                 if block_bss else None),
        "regimes": _regime_bss(oos),
        "per_block": blocks,
    }
    if mae:
        weight = sum(m[2] for m in mae)
        summary["expected_return_mae"] = sum(m[0] * m[2] for m in mae) / weight
        summary["expected_return_mae_constant"] = sum(m[1] * m[2] for m in mae) / weight
    if probability_threshold is not None:
        # Measures hypothesis 2.3: how often the probability condition holds
        # out of sample, compared with the observed base rate.
        summary["probability_threshold"] = float(probability_threshold)
        summary["share_model_above_threshold"] = float(np.mean(pm >= probability_threshold))
        summary["share_climatology_above_threshold"] = float(np.mean(pc >= probability_threshold))
    summary["proposed_status"], summary["proposed_status_reasons"] = proposed_status(summary, gate)
    return summary


def compact(summary: dict) -> dict:
    """Subset for the e-mail / per-ETF result (full detail stays in the report)."""
    keys = ["mode", "status", "proposed_status", "proposed_status_reasons", "oos_start",
            "oos_end", "oos_rows", "n_eff", "blocks", "bss", "bss_ci_low", "bss_ci_high",
            "bss_logistic", "brier_model", "brier_climatology", "brier_logistic",
            "positive_block_share", "calibration_slope", "base_rate_oos",
            "share_model_above_threshold", "probability_threshold", "computed_at"]
    return {k: summary.get(k) for k in keys if k in summary}
