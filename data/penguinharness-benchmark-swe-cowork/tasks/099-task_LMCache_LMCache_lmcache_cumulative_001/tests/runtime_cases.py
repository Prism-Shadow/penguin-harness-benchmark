from __future__ import annotations

import importlib
import os
import subprocess
import sys

import pytest


def object_identity():
    from lmcache.v1.distributed.api import ObjectKey

    keys = []
    for chunk in (b"", b"\x00\xff\x10", b"independent-hash"):
        for salt in ("", "tenant-alpha", "tenant-beta"):
            key = ObjectKey(chunk, "different-model", 7, 4, salt)
            encoded = key.to_encoded_object_key()
            assert encoded.chunk_hash_hex == chunk.hex()
            assert encoded.to_object_key() == key
            keys.append(key)
    assert len(set(keys)) == len(keys)
    for salt in ("/", "left/right", "trailing/"):
        with pytest.raises(ValueError):
            ObjectKey(b"arbitrary", "model", 0, cache_salt=salt)


def allocator_lifecycle():
    import torch
    from lmcache.v1 import memory_management
    from lmcache.v1.memory_allocators.buffer_allocator import BufferAllocator
    from lmcache.v1.memory_allocators.host_memory_allocator import HostMemoryAllocator

    for allocator_type in (BufferAllocator, memory_management.BufferAllocator):
        allocator = allocator_type("cpu")
        for length in (0, 3, 29):
            values = allocator.batched_allocate(torch.Size([length]), torch.uint8, 3)
            assert len(values) == 3
            assert [len(value.byte_array) for value in values] == [length] * 3
            for index, value in enumerate(values):
                value.byte_array[:] = bytes([41 + index]) * length
            for index, value in enumerate(values):
                assert bytes(value.byte_array) == bytes([41 + index]) * length
            allocator.batched_free(values)
        with pytest.raises((ValueError, OverflowError)):
            allocator.allocate(torch.Size([-1]), torch.uint8)
        assert allocator.memcheck()
    for allocator_type in (HostMemoryAllocator, memory_management.HostMemoryAllocator):
        allocator = allocator_type(8192)
        shape = torch.Size([2, 1, 32, 64])
        first = allocator.allocate(shape, torch.float16)
        assert first is not None and first.tensor.shape == shape
        first.tensor.fill_(6)
        assert torch.all(first.tensor == 6)
        assert allocator.allocate(shape, torch.float16) is None
        allocator.free(first)
        restored = allocator.allocate(shape, torch.float16)
        assert restored is not None
        allocator.free(restored)
        assert allocator.memcheck()


def device_registry():
    for requested in ("cpu", " CPU ", "not-a-device"):
        environment = dict(os.environ, DEVICE_TYPE=requested)
        result = subprocess.run([
            sys.executable, "-c",
            "from lmcache.v1.platform import get_device_spec, get_torch_device, resolve_device_ops; "
            "assert get_torch_device()[1] == 'cpu'; "
            "assert isinstance(get_device_spec('cpu').is_available(), bool); "
            "assert get_device_spec('not-a-device') is None; "
            "assert resolve_device_ops('cpu').device_type == 'cpu'",
        ], env=environment, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr


def device_info_compatibility():
    from lmcache.v1.platform.base_device_info import DeviceInfo

    class CallerDevice(DeviceInfo):
        device_type = "caller-device"
        torch_module_name = "cpu"
        ops_module = None

        def is_available(self):
            return True

    device = CallerDevice()
    assert device.is_available() and device.is_handle_transfer_available()
    assert device.device_type == "caller-device" and device.pin_memory_backend is None
    for name in ("base_device_spec", "base.device_spec"):
        module = importlib.import_module(f"lmcache.v1.platform.{name}")
        with pytest.raises(NotImplementedError):
            module.DeviceSpec().create_cache_context([])


def timeout_bridge():
    from integration_cases import run_isolated
    run_isolated("timeout_constructor_contract")


def coordinator_routes():
    from fastapi.testclient import TestClient
    from lmcache.v1.mp_coordinator.app import create_app
    from lmcache.v1.mp_coordinator.config import MPCoordinatorConfig

    app = create_app(MPCoordinatorConfig(health_check_interval=0, eviction_check_interval=0))
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200 and response.json() == {"status": "healthy"}
        response = client.get("/instances")
        assert response.status_code == 200 and response.json() == {"instances": []}
        assert client.get("/not-a-coordinator-route").status_code == 404


def directory_lifecycle():
    from lmcache.v1.distributed.api import ObjectKey, Tier
    from lmcache.v1.mp_coordinator.api import CacheEventBatch, CacheEventEntry, CacheEventType
    from lmcache.v1.mp_coordinator.key_directory import KeyDirectory

    directory = KeyDirectory()
    ingest = getattr(directory, "consume", None) or directory.apply_batch
    key = ObjectKey(b"lifecycle", "new-model", 2)
    missing = ObjectKey(b"absent", "new-model", 2)
    entry = CacheEventEntry(key.to_encoded_object_key(), size_bytes=39, token_ids=[8, 1, 7])
    ingest(CacheEventBatch("emitter", 1, 1, CacheEventType.STORE, Tier.L2, "disk", [entry]))
    assert len(directory.lookup([key])[0]) == 1
    assert directory.lookup([key, missing])[1] == []
    assert directory.get_token_ids([key.chunk_hash, missing.chunk_hash]) == [(8, 1, 7), ()]
    ingest(CacheEventBatch("emitter", 1, 2, CacheEventType.DELETE, Tier.L2, "disk", [entry]))
    assert directory.lookup([key]) == [[]]
    ingest(CacheEventBatch("emitter", 1, 3, CacheEventType.STORE, Tier.L2, "disk", [entry]))
    assert directory.lookup([key])[0][0].size_bytes == 39


def blend_lifecycle():
    import numpy as np
    from lmcache.v1.mp_coordinator.blend_index import BlendIndex

    for size, stride in ((0, 1), (3, 0), (-1, 2)):
        with pytest.raises(ValueError):
            BlendIndex(chunk_size=size, probe_stride=stride)
    for tokens in ([7, 2, 9], [11, 12, 13]):
        index = BlendIndex(chunk_size=3)
        values = np.array(tokens, dtype=np.int64)
        index.add(values, b"first", 5)
        index.add(values, b"second", 17)
        query = np.array([101, *tokens, 202], dtype=np.int64)
        matches = {(match.chunk_hash, match.old_st, match.cur_st) for match in index.match(query)}
        assert matches and matches <= {(b"first", 5, 1), (b"second", 17, 1)}
        assert index.match(np.array([tokens[0], 500, tokens[2]], dtype=np.int64)) == []
        assert index.match(values[:2]) == []
        index.remove(values, b"first")
        assert [match.chunk_hash for match in index.match(query)] == [b"second"]
        index.remove(values, b"second")
        assert index.match(query) == []
        index.add(values, b"original", 23)
        different = np.array([43, 17, 61], dtype=np.int64)
        index.add(different, b"different", 31)
        combined = np.concatenate((values, different))
        assert {(match.chunk_hash, match.old_st, match.cur_st) for match in index.match(combined)} == {
            (b"original", 23, 0), (b"different", 31, 3)}
