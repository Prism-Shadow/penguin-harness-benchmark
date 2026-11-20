from capture_contract import make_strategy, select_strategy


def test_contract(monkeypatch):
    from mss.models import Monitor

    calls = []
    monitors = [Monitor(left=0, top=0, width=3, height=2)]
    def grab(region):
        calls.append(("grab", region.left, region.top, region.width, region.height))
        return bytearray((3, 2, 1, 255)) * region.width * region.height

    implementation = make_strategy(monitors, grab, lambda: calls.append("close"))
    selections = []
    def factory():
        selections.append(implementation)
        return implementation

    capture_type = select_strategy(monkeypatch, factory)
    with capture_type() as capture:
        assert capture.monitors is monitors
        for region in ((0, 0, 1, 1), (1, 0, 3, 2)):
            image = capture.grab(region)
            assert bytes(image.bgra) == bytes((3, 2, 1, 255)) * image.width * image.height
    assert selections == [implementation]
    assert calls == [("grab", 0, 0, 1, 1), ("grab", 1, 0, 2, 2), "close"]
