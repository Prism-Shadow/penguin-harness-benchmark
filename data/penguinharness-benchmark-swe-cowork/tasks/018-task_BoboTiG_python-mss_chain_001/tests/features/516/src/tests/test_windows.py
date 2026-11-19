from windows_contract import WindowsNative


def test_contract(monkeypatch):
    native = WindowsNative(monkeypatch)
    with native.capture() as capture:
        assert native.calls["GetWindowDC"] + native.calls["GetDC"] == 0
        assert native.calls["CreateCompatibleDC"] == 0
        image = capture.grab((1, 2, 3, 5))
        assert image.size == (2, 3)
        assert bytes(image.bgra) == bytes((1, 7, 19, 255)) * 6
        assert native.calls["GetWindowDC"] + native.calls["GetDC"] > 0
        assert native.calls["CreateCompatibleDC"] > 0
    assert not native.desktop_dcs and not native.memory_dcs and not native.storage
