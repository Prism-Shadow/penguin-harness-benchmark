from __future__ import annotations
import importlib
def test_platform_base_device_spec_is_importable_from_new_package():
    module = importlib.import_module("lmcache.v1.platform.base.device_spec")
    spec = module.DeviceSpec()
    assert hasattr(spec, "device_type") and hasattr(spec, "is_available")
