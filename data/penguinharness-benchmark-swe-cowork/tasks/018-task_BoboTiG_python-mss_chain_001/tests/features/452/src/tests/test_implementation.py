from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    capture_type = select_strategy(monkeypatch, make_strategy)
    with capture_type() as first, capture_type() as second:
        assert first._lock is not second._lock
        assert first._lock.acquire(blocking=False)
        try:
            assert second._lock.acquire(blocking=False)
            second._lock.release()
        finally:
            first._lock.release()
