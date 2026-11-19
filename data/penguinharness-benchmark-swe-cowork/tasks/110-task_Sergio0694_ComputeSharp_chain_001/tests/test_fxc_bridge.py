import concurrent.futures
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compiler_check', ROOT / 'environment/build-support/check_compiler.py')
compiler_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler_check)


class Macro(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char_p), ('definition', ctypes.c_char_p)]


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix='fxc-transport-')
        cls.directory = Path(cls.scratch.name)
        cls.library = cls.directory / 'libd3dcompiler_47.so'
        subprocess.run(['gcc', '-std=c11', '-shared', '-fPIC', '-pthread', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-o', str(cls.library), str(ROOT / 'environment/native-runtime/fxc_bridge.c')], check=True)
        cls.native = ctypes.CDLL(str(cls.library))
        cls.compile = cls.native.D3DCompile
        cls.compile.restype = ctypes.c_int32
        cls.compile.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32,
                               ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        cls.host = cls.directory / 'protocol-fixture'
        cls.host.write_text(f'#!{sys.executable}\n' + (ROOT / 'tests/fxc_protocol_fixture.py').read_text())
        cls.host.chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.environment = patch.dict(os.environ, COWORK_FXC_HOST=str(self.host))
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def request(self, source, include=None, entry=b'Execute', target=b'ps_4_0'):
        macros = (Macro * 3)(Macro(b'D2D_FULL_SHADER', b''), Macro(b'D2D_ENTRY', b'Execute'), Macro(None, None))
        output, errors = ctypes.c_void_p(), ctypes.c_void_p()
        status = self.compile(source, len(source), b'input.hlsl', macros, include, entry, target,
                              0x8128, 7, ctypes.byref(output), ctypes.byref(errors))
        return status, compiler_check.blob_bytes(output), compiler_check.blob_bytes(errors)

    def test_compile_marshals_all_arguments_and_nullable_library_entry(self):
        status, output, errors = self.request(b'transport payload', entry=None, target=b'lib_5_0')
        self.assertEqual((status, errors), (0, b''))
        request = json.loads(output)
        self.assertEqual(request, {'operation': 1, 'source': 'transport payload', 'name': 'input.hlsl',
                                  'macros': [['D2D_FULL_SHADER', ''], ['D2D_ENTRY', 'Execute']],
                                  'entry': None, 'target': 'lib_5_0', 'flags': 0x8128, 'effects': 7, 'include_mode': 0})

    def test_concurrent_calls_are_isolated(self):
        counter = self.native.CoworkFxcCompileCount
        counter.restype = ctypes.c_uint64
        before = counter()
        sources = [f'request-{index}'.encode() for index in range(12)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.request, sources))
        self.assertEqual([json.loads(output)['source'] for _, output, _ in results], [value.decode() for value in sources])
        self.assertEqual(counter() - before, len(sources))

    def test_failure_diagnostics_abort_and_oversized_response(self):
        status, output, errors = self.request(b'negative')
        self.assertLess(status, 0)
        self.assertEqual((output, errors), (b'', b'compiler diagnostic'))
        for source in (b'abort', b'oversized'):
            with self.subTest(source=source):
                status, output, errors = self.request(source)
                self.assertLess(status, 0)
                self.assertFalse(output)
                self.assertIn(b'FXC backend failed', errors)

    def test_missing_backend_fails_closed(self):
        for host in (str(self.directory / 'missing'), '/bin/false'):
            with self.subTest(host=host), patch.dict(os.environ, COWORK_FXC_HOST=host):
                status, output, errors = self.request(b'source')
                self.assertLess(status, 0)
                self.assertFalse(output)
                self.assertTrue(errors)

    def test_include_callbacks_preserve_parent_and_close_lifecycle(self):
        opened, closed, parents = [], [], []
        buffers = [ctypes.create_string_buffer(b'root content'), ctypes.create_string_buffer(b'nested content')]
        open_type = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p,
                                     ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32))
        close_type = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)

        @open_type
        def open_include(instance, kind, name, parent, output, length):
            index = len(opened)
            opened.append((kind, name))
            parents.append(parent)
            output[0], length[0] = ctypes.addressof(buffers[index]), len(buffers[index].value)
            return 0

        @close_type
        def close_include(instance, address):
            closed.append(address)
            return 0

        table = (ctypes.c_void_p * 2)(ctypes.cast(open_include, ctypes.c_void_p), ctypes.cast(close_include, ctypes.c_void_p))
        instance = ctypes.pointer(table)
        status, output, errors = self.request(b'include', ctypes.byref(instance))
        self.assertEqual((status, errors), (0, b''))
        self.assertEqual(opened, [(0, b'root.hlsli'), (0, b'nested.hlsli')])
        self.assertEqual(parents, [None, ctypes.addressof(buffers[0])])
        self.assertEqual(closed, [ctypes.addressof(buffers[1]), ctypes.addressof(buffers[0])])
        self.assertEqual(json.loads(output)['includes'], [[0, 'root content'], [0, 'nested content']])

    def test_set_part_and_disassembly_use_the_backend(self):
        set_part = self.native.D3DSetBlobPart
        set_part.restype = ctypes.c_int32
        set_part.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32,
                            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        output = ctypes.c_void_p()
        self.assertEqual(set_part(b'bytecode', 8, 10, 5, b'library', 7, ctypes.byref(output)), 0)
        self.assertEqual(json.loads(compiler_check.blob_bytes(output)),
                         {'operation': 2, 'source': 'bytecode', 'part': 10, 'flags': 5, 'extra': 'library'})
        disassemble = self.native.D3DDisassemble
        disassemble.restype = ctypes.c_int32
        disassemble.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32,
                               ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
        self.assertEqual(disassemble(b'bytecode', 8, 2, b'annotation', ctypes.byref(output)), 0)
        self.assertEqual(json.loads(compiler_check.blob_bytes(output)),
                         {'operation': 3, 'source': 'bytecode', 'flags': 2, 'comments': 'annotation'})

    def test_protocol_fixture_cannot_pass_real_compiler_preflight(self):
        observations = compiler_check.check_compiler(str(self.library))
        self.assertFalse(all(item['passed'] for item in observations))
        self.assertFalse(any(item['passed'] for item in observations if item['kind'] == 'valid'))


if __name__ == '__main__':
    unittest.main()
