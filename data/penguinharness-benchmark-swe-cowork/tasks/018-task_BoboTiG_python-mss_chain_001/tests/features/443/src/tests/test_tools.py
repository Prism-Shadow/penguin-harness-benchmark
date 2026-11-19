import warnings
from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    calls = []
    with warnings.catch_warnings(record=True) as notices:
        warnings.simplefilter("always")
        _exercise(monkeypatch, calls)
    assert not notices, [str(notice.message) for notice in notices]


def _exercise(monkeypatch, calls):
    capture_type = select_strategy(monkeypatch, lambda: make_strategy(close=lambda: calls.append("close")))
    with capture_type() as capture:
        capture.close()
        capture.close()
    assert calls == ["close"]
    with capture_type():
        pass
    assert calls == ["close", "close"]
