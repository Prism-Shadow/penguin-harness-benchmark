from runtime_cases import device_registry

def test_device_registry():
    device_registry()


def test_backend_registrations_remain_queryable_without_hardware():
    from lmcache.v1.platform import get_device_spec
    for backend in ("cpu", "cuda", "hpu", "musa", "xpu", "sycl"):
        spec = get_device_spec(backend)
        assert spec is not None, backend
        assert isinstance(spec.is_available(), bool)
    assert get_device_spec("unknown-backend") is None
