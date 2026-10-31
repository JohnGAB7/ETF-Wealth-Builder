import re

from src.config import load_yaml

ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _isin_checksum_ok(isin: str) -> bool:
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return (10 - total % 10) % 10 == int(isin[-1])


def test_universe_entries_are_complete_and_unique():
    etfs = load_yaml("config/etf_universe.yaml")["etfs"]
    ids = [e["id"] for e in etfs]
    assert len(ids) == len(set(ids))
    assert len({e["yahoo_symbol"] for e in etfs}) == len(etfs)
    for etf in etfs:
        for key in ("id", "name", "isin", "yahoo_symbol", "currency", "constituents_file"):
            assert etf.get(key), (etf.get("id"), key)
        assert ISIN.match(etf["isin"]) and _isin_checksum_ok(etf["isin"]), etf["isin"]
        assert etf["currency"] in {"EUR", "USD"}
