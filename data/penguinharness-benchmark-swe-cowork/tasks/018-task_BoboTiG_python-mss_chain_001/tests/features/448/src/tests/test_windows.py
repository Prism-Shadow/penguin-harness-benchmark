import pytest
from windows_contract import WindowsNative


def test_contract(monkeypatch):
    native = WindowsNative(monkeypatch)
    from mss.exception import ScreenShotError

    with native.capture() as capture:
        assert bytes(capture.grab((0, 0, 2, 2)).bgra) == bytes((1, 7, 19, 255)) * 4
        for failing in ("BitBlt", "GdiFlush", "CreateDIBSection"):
            native.error_code = 5
            native.fail[failing] = 0
            with pytest.raises(ScreenShotError) as captured:
                capture.grab((1, 2, 4, 6))
            arguments = [args for name, args in native.events if name == failing][-1]
            assert captured.value.details["func"] == failing
            assert captured.value.details["args"] == arguments
            assert isinstance(captured.value.details["args"], tuple)
            assert captured.value.details["error_msg"]
            assert not native.desktop_dcs and not native.memory_dcs
            native.fail.clear()
            image = capture.grab((1, 2, 4, 6))
            assert bytes(image.bgra) == bytes((native.frame, 7, 19, 255)) * 12
            # Force the next iteration to allocate a different-sized DIB.
            capture.grab((0, 0, 2, 2))
    assert native.calls["ReleaseDC"] == native.calls["GetWindowDC"] + native.calls["GetDC"]
    assert native.calls["DeleteDC"] == native.calls["CreateCompatibleDC"]
    assert not native.desktop_dcs and not native.memory_dcs and not native.storage
