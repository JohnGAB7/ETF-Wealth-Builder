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


@pytest.fixture
def mocked(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(main, "get_macro_snapshot", lambda: {"ecb_deposit_facility_rate": 2.0,
                                                             "ecb_deposit_facility_rate_date": "2026-10-29"})
    monkeypatch.setattr(main, "get_market_news", lambda: [])
    monkeypatch.setattr(main, "get_history",
                        lambda symbol: _history() if symbol != "EIMI.L" else pd.DataFrame())
    monkeypatch.setattr(main, "get_valuations", lambda tickers: {})
    monkeypatch.setattr(main, "write_report", lambda report: tmp_path / "report.json")
    monkeypatch.setattr(main, "send_digest", lambda *a, **k: sent.append(("digest", a, k)) or True)
    monkeypatch.setattr(main, "send_signal_alert", lambda *a, **k: sent.append(("alert", a, k)) or True)
    return sent


def test_run_once_produces_results_and_one_digest(mocked):
    report = main.run_once()
    ids = {r["id"]: r for r in report["etfs"]}
    assert ids["eimi"]["status"] == "INSUFFICIENT_PRICE_HISTORY"
    assert ids["eimi"]["symbol"] == "EIMI.L" and ids["eimi"]["currency"] == "USD"
    estimated = [r for r in report["etfs"] if r.get("prob_positive") is not None]
    assert estimated, "at least one ETF should receive a model estimate"
    for r in estimated:
        assert 0.0 <= r["prob_positive"] <= 1.0
        assert "base_rate_positive" in r and "brier_reference" in r["validation"]
        assert len(r["as_of"]) == 10  # date only
    digests = [s for s in mocked if s[0] == "digest"]
    assert len(digests) == 1
    assert digests[0][2]["strategy"]["primary_horizon_days"] == 63


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
