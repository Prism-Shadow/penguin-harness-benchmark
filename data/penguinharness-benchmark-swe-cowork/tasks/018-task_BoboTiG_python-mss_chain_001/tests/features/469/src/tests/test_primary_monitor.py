import dataclasses
from collections import UserDict
from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    from mss.models import Monitor
    for convert in (lambda x: x, dataclasses.asdict, lambda x: UserDict(dataclasses.asdict(x))):
        for primary in (True, False):
            monitors = [convert(Monitor(left=0, top=0, width=300, height=100, is_primary=True)),
                        convert(Monitor(left=0, top=0, width=100, height=100, is_primary=False)),
                        convert(Monitor(left=100, top=0, width=200, height=100, is_primary=primary))]
            capture_type = select_strategy(monkeypatch, lambda: make_strategy(monitors=monitors))
            with capture_type() as capture:
                assert capture.primary_monitor is monitors[2 if primary else 1]
                assert capture.monitors is monitors
