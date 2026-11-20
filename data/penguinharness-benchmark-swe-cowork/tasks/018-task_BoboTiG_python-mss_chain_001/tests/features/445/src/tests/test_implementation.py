import pytest
from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    from mss.exception import ScreenShotError

    calls = []
    def grab(region):
        calls.append(region)
        return bytearray((1, 2, 3, 255)) * region.width * region.height

    capture_type = select_strategy(monkeypatch, lambda: make_strategy(grab=grab))
    with capture_type() as capture:
        for region in [(-1, 0, 10, 10), (0, -1, 10, 10), (10, 0, 5, 10), (0, 10, 10, 5)]:
            with pytest.raises(ScreenShotError):
                capture.grab(region)
        assert calls == []
        image = capture.grab((2, 3, 5, 7))
        assert image.size == (3, 4)
        assert bytes(image.bgra) == bytes((1, 2, 3, 255)) * 12
        assert (calls[0].left, calls[0].top, calls[0].width, calls[0].height) == (2, 3, 3, 4)
