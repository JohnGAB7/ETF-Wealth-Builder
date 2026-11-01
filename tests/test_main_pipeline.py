"""Integration test of one monitoring cycle with every provider mocked."""
import numpy as np
import pandas as pd
import pytest

import src.main as main


def _history(n=900, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.now(tz="UTC").date(), periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    return pd.DataFrame({"Close": close}, index=idx)


class _Sent(list):
    validations: list


@pytest.fixture
def mocked(monkeypatch, tmp_path):
    sent = _Sent()
    monkeypatch.setattr(main, "get_macro_snapshot", lambda: {"ecb_deposit_facility_rate": 2.0,
                                                             "ecb_deposit_facility_rate_date": "2026-10-29"})
    monkeypatch.setattr(main, "get_market_news", lambda: [])
    monkeypatch.setattr(main, "get_history",
                        lambda symbol: _history() if symbol != "EMIM.AS" else pd.DataFrame())
    monkeypatch.setattr(main, "get_valuations", lambda tickers: {})
    monkeypatch.setattr(main, "write_report", lambda report: tmp_path / "report.json")
    state_path = tmp_path / "alert_state.json"
    monkeypatch.setattr(main, "load_state", lambda: __import__(
        "src.state.alert_state", fromlist=["x"]).load_state(state_path))
    monkeypatch.setattr(main, "save_state", lambda state: __import__(
        "src.state.alert_state", fromlist=["x"]).save_state(state, state_path))
    monkeypatch.setattr(main, "send_digest", lambda *a, **k: sent.append(("digest", a, k)) or True)
    monkeypatch.setattr(main, "send_signal_alert", lambda *a, **k: sent.append(("alert", a, k)) or True)
    # The purged walk-forward is tested in test_validation.py; here a stub that
    # always says NOT_VALIDATED shows that observation mode never alters a signal.
    validations = []

    def _stub_validation(frame, **kwargs):
        validations.append(kwargs)
        return {"mode": "observation", "status": "EVALUATED", "proposed_status": "NOT_VALIDATED",
                "proposed_status_reasons": ["stub"], "bss": -0.1, "n_eff": 5.0, "blocks": 2}

    monkeypatch.setattr(main, "walk_forward_validate", _stub_validation)
    sent.validations = validations
    return sent


def test_run_once_produces_results_and_one_digest(mocked):
    report = main.run_once()
    ids = {r["id"]: r for r in report["etfs"]}
    assert ids["eimi"]["status"] == "INSUFFICIENT_PRICE_HISTORY"
    assert ids["eimi"]["symbol"] == "EMIM.AS" and ids["eimi"]["currency"] == "EUR"
    estimated = [r for r in report["etfs"] if r.get("prob_positive") is not None]
    assert estimated, "at least one ETF should receive a model estimate"
    for r in estimated:
        assert 0.0 <= r["prob_positive"] <= 1.0
        assert "base_rate_positive" in r and "brier_reference" in r["validation"]
        assert len(r["as_of"]) == 10  # date only
    digests = [s for s in mocked if s[0] == "digest"]
    assert len(digests) == 1
    assert digests[0][2]["strategy"]["primary_horizon_days"] == 63
    for r in estimated:
        assert r["validation_oos"]["mode"] == "observation"
        assert r["validation_oos"]["computed_at"] == report["retrieved_at"][:10]
    first_calls = len(mocked.validations)
    assert first_calls == len(estimated)
    assert mocked.validations[0]["horizon"] == 63 and mocked.validations[0]["test_block"] == 126
    main.run_once()  # same day: every validation comes from the weekly cache
    assert len(mocked.validations) == first_calls


def test_notification_failure_does_not_abort_cycle(monkeypatch, mocked, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(main, "send_digest", boom)
    report = main.run_once()
    assert report["etfs"]
    assert "Notification 'daily digest' failed: RuntimeError" in caplog.text


def test_report_is_written_before_notifications(monkeypatch, mocked, tmp_path):
    order = []
    monkeypatch.setattr(main, "write_report", lambda r: order.append("report") or tmp_path / "r.json")
    monkeypatch.setattr(main, "send_digest", lambda *a, **k: order.append("digest") or True)
    main.run_once()
    assert order == ["report", "digest"]


def test_stale_price_blocks_review_signal(monkeypatch, mocked):
    # History ending long before the run date: any signal must fail closed.
    old = _history()
    old.index = old.index - pd.Timedelta(days=60)
    monkeypatch.setattr(main, "get_history", lambda symbol: old)
    report = main.run_once()
    for r in report["etfs"]:
        if r.get("prob_positive") is not None:
            assert r["price_stale"] is True
            assert r["signal"] == "INSUFFICIENT_EVIDENCE"
    assert not [s for s in mocked if s[0] == "alert"]


def test_alert_sent_once_across_runs(monkeypatch, mocked):
    # Force a review signal on every enabled ETF with a fresh price.
    monkeypatch.setattr(main, "classify_signal", lambda *a, **k: "BUY_OPPORTUNITY_REVIEW")
    main.run_once()
    first = len([s for s in mocked if s[0] == "alert"])
    assert first >= 1  # the stub says NOT_VALIDATED: observation mode blocks nothing
    report = main.run_once()
    assert len([s for s in mocked if s[0] == "alert"]) == first  # no repeat
    estimated = [r for r in report["etfs"] if r.get("prob_positive") is not None]
    assert all(r["previous_signal"] == "BUY_OPPORTUNITY_REVIEW" for r in estimated)
