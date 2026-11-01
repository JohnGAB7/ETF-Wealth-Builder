"""Purged walk-forward validation (lot 5.1, observation mode)."""
import numpy as np
import pandas as pd
import pytest

from src.models import validation as v
from src.state import validation_cache as vc

H = 63


def _fast_model(horizon):
    """Logistic stand-in so tests stay fast; the protocol is what is tested."""
    return v.logistic_factory(horizon)


def _frame(n=1400, seed=0, signal=0.0):
    """Random walk features; with `signal` > 0 a feature predicts the label."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    x = rng.normal(size=(n, len(v.FEATURES)))
    frame = pd.DataFrame(x, index=idx, columns=v.FEATURES)
    noise = rng.normal(size=n)
    latent = signal * frame["momentum_21d"].to_numpy() + noise
    frame["forward_return"] = latent / 100
    frame["positive_forward_return"] = (latent > 0).astype(float)
    return frame


# ------------------------------------------------------------------ splits

def test_purge_removes_every_overlapping_training_label():
    splits = v.purged_walk_forward_splits(1400, H, 500, 126)
    assert splits
    for train, test in splits:
        # label of row t uses prices up to t + H: must end before the test starts
        assert train.max() + H < test.min()
        assert len(train) >= 500


def test_splits_are_contiguous_and_cover_the_tail():
    splits = v.purged_walk_forward_splits(1400, H, 500, 126)
    tests = np.concatenate([t for _, t in splits])
    assert tests[0] == 500 + H and tests[-1] == 1399
    assert np.all(np.diff(tests) == 1)


def test_inner_calibration_folds_are_purged():
    for fit, cal in v.purged_inner_splits(900, H):
        assert fit.max() + H < cal.min()


def test_no_split_when_history_too_short():
    assert v.purged_walk_forward_splits(560, H, 500, 126) == []
    out = v.walk_forward_validate(_frame(560), horizon=H, model_factory=_fast_model(H))
    assert out["status"] == v.INSUFFICIENT_HISTORY
    assert out["proposed_status"] == v.INSUFFICIENT_HISTORY


def test_purge_gap_is_exactly_the_horizon():
    """Labels overlap over H sessions: exactly H rows separate train from test."""
    for train, test in v.purged_walk_forward_splits(1400, H, 500, 126):
        assert test.min() - train.max() - 1 == H


def test_overlapping_labels_make_unpurged_validation_optimistic():
    """Persistent labels (63-day windows) let an unpurged split 'see' the test.

    With labels built from overlapping windows of pure noise, the last unpurged
    training rows share most of their window with the first test rows, so their
    labels largely coincide. The purged split removes exactly those rows.
    """
    rng = np.random.default_rng(9)
    n = 1400
    shocks = rng.normal(size=n + H)
    window_sum = np.convolve(shocks, np.ones(H), "valid")[1:n + 1]  # sum of t+1..t+H
    label = (window_sum > 0).astype(int)
    t0 = 1000
    unpurged_train = np.arange(0, t0)
    purged_train = np.arange(0, t0 - H)
    test = np.arange(t0, t0 + 126)
    # first test labels are mostly identical to the last unpurged training labels
    agreement = np.mean(label[unpurged_train[-10:]] == label[test[:10]])
    assert agreement >= 0.8
    assert purged_train.max() + H < test.min()


# ----------------------------------------------------------------- metrics

def test_metrics_basic_values():
    y = np.array([1, 0, 1, 1])
    p = np.array([0.8, 0.2, 0.6, 0.9])
    assert v.brier(y, p) == pytest.approx(np.mean([0.04, 0.04, 0.16, 0.01]))
    assert v.skill(0.2, 0.25) == pytest.approx(0.2)
    assert v.log_loss(np.array([1]), np.array([1.0])) == pytest.approx(-np.log(1 - 1e-3))


def test_bootstrap_is_reproducible_and_brackets_estimate():
    rng = np.random.default_rng(1)
    y = (rng.random(1000) < 0.6).astype(int)
    pm = np.clip(0.6 + 0.2 * (y - 0.6) + rng.normal(0, 0.05, 1000), 0, 1)
    pc = np.full(1000, 0.6)
    a = v.block_bootstrap_bss(y, pm, pc, block=H, draws=300, seed=7)
    b = v.block_bootstrap_bss(y, pm, pc, block=H, draws=300, seed=7)
    assert a == b
    point = v.skill(v.brier(y, pm), v.brier(y, pc))
    assert a[0] <= point <= a[1]


def test_diebold_mariano_sign():
    rng = np.random.default_rng(2)
    y = (rng.random(800) < 0.5).astype(int)
    good = np.where(y == 1, 0.7, 0.3)
    stat, p = v.diebold_mariano(y, good, np.full(800, 0.5), lags=5)
    assert stat > 0 and p < 0.01


def test_calibration_slope_near_one_for_calibrated_forecasts():
    rng = np.random.default_rng(4)
    p = rng.uniform(0.2, 0.8, 5000)
    y = (rng.random(5000) < p).astype(int)
    slope, intercept = v.calibration_slope(y, p)
    assert 0.8 < slope < 1.2 and abs(intercept) < 0.2


# -------------------------------------------------------------- end to end

def test_random_walk_is_not_validated():
    out = v.walk_forward_validate(_frame(1400, seed=5), horizon=H,
                                  model_factory=_fast_model(H), bootstrap_draws=200,
                                  probability_threshold=0.62, with_expected_return=False)
    assert out["status"] == "EVALUATED" and out["mode"] == "observation"
    assert out["n_eff"] == pytest.approx(out["oos_rows"] / H, abs=0.1)
    assert out["proposed_status"] == v.NOT_VALIDATED
    assert out["proposed_status_reasons"]
    assert 0.0 <= out["share_model_above_threshold"] <= 1.0


def test_planted_signal_is_validated():
    out = v.walk_forward_validate(_frame(3000, seed=6, signal=2.0), horizon=H,
                                  model_factory=_fast_model(H), bootstrap_draws=200,
                                  with_expected_return=False)
    assert out["bss"] > 0.2
    assert out["bss_ci_low"] > 0
    assert out["proposed_status"] == v.VALIDATED, out["proposed_status_reasons"]


def test_climatology_uses_training_rows_only():
    frame = _frame(1400, seed=8)
    out = v.walk_forward_validate(frame, horizon=H, model_factory=_fast_model(H),
                                  bootstrap_draws=50, with_expected_return=False)
    y = frame["positive_forward_return"].to_numpy()
    for block, (train, _) in zip(out["per_block"],
                                 v.purged_walk_forward_splits(len(frame), H, 500, 126)):
        assert block["base_rate_train"] == pytest.approx(y[train].mean())


def test_gate_reasons_are_explicit():
    status, reasons = v.proposed_status({"status": "EVALUATED", "n_eff": 10, "bss_ci_low": -0.1,
                                         "positive_block_share": 0.4, "calibration_slope": 3.0,
                                         "brier_model": 0.25, "brier_logistic": 0.2})
    assert status == v.NOT_VALIDATED and len(reasons) == 5


# -------------------------------------------------------------------- cache

def test_cache_fresh_within_refresh_days_only(tmp_path):
    cache = vc.load_cache(tmp_path / "c.json")
    fp = vc.fingerprint("VWCE.DE", "2019-07-23", 63, 126)
    vc.put(cache, "vwce", fp, "2026-11-01", {"bss": 0.01})
    vc.save_cache(cache, tmp_path / "c.json")
    cache = vc.load_cache(tmp_path / "c.json")
    assert vc.get_fresh(cache, "vwce", fp, "2026-11-07", 7) == {"bss": 0.01}
    assert vc.get_fresh(cache, "vwce", fp, "2026-11-08", 7) is None
    other = vc.fingerprint("VWCE.DE", "2019-07-23", 21, 126)
    assert vc.get_fresh(cache, "vwce", other, "2026-11-02", 7) is None


def test_unreadable_cache_means_recompute(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json", encoding="utf-8")
    assert vc.load_cache(path) == {"version": vc.CACHE_VERSION, "etfs": {}}
