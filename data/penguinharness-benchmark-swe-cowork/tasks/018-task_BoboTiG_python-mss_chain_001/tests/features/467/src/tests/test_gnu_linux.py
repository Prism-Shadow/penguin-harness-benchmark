import pytest
from capture_contract import replace_public_callable
from x11_contract import NativeTrace, xserver


def test_contract(monkeypatch, tmp_path):
    native = NativeTrace(monkeypatch)
    import mss
    import mss.buffer as buffer

    interruption = KeyboardInterrupt("conversion interrupted")
    conversions = []
    def interrupt(data, finalizer):
        conversions.append(len(data))
        if isinstance(data, memoryview):
            data.release()
        raise interruption

    with xserver(tmp_path) as display:
        with mss.mss(backend="xshmgetimage", display=display) as capture:
            with monkeypatch.context() as scoped:
                replace_public_callable(scoped, buffer, "finalizing_buffer", interrupt)
                with pytest.raises(KeyboardInterrupt) as captured:
                    capture.grab((0, 0, 2, 2))
                assert captured.value is interruption
            assert conversions == [16]
            assert bytes(capture.grab((0, 0, 2, 2)).rgb) == bytes(12)
        native.assert_released()
