from __future__ import annotations

import platform
import sys


def select_strategy(monkeypatch, factory):
    """Replace the documented platform dispatch boundary, not a facade private alias."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    import mss
    import mss.linux as module

    replace_public_callable(monkeypatch, module, "choose_impl", lambda *args, **kwargs: factory())
    return mss.mss


def make_strategy(monitors=None, grab=None, close=None):
    class Strategy:
        def __init__(self):
            self.with_cursor = False
            self.performance_status = []

        def monitors(self):
            return monitors if monitors is not None else []

        def cursor(self):
            return None

        def grab(self, region):
            if grab is not None:
                return grab(region)
            return bytearray((3, 2, 1, 255)) * (region.width * region.height)

        def close(self):
            if close is not None:
                close()

    return Strategy()


def replace_public_callable(monkeypatch, module, name, replacement):
    original = getattr(module, name)
    for loaded_name, loaded in list(sys.modules.items()):
        if loaded_name == "mss" or loaded_name.startswith("mss."):
            for binding, value in list(vars(loaded).items()):
                if value is original:
                    monkeypatch.setattr(loaded, binding, replacement)
