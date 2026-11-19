import pytest
from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    calls = []
    cleanup_error = RuntimeError("cleanup failed")
    body_error = ValueError("body failed")
    def close():
        calls.append("close")
        raise cleanup_error

    capture_type = select_strategy(monkeypatch, lambda: make_strategy(close=close))
    with pytest.raises(ValueError) as captured:
        with capture_type():
            raise body_error
    assert captured.value is body_error
    with pytest.raises(RuntimeError) as captured:
        with capture_type():
            pass
    assert captured.value is cleanup_error
    assert calls == ["close", "close"]
