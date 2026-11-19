import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
SPEC = importlib.util.spec_from_file_location('contract_slice', ROOT / 'tests/contract_slice.py')
SLICE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SLICE)


class ContractSliceTests(unittest.TestCase):
    def test_unrelated_legacy_encoded_source_is_not_a_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Client').mkdir()
            (root / 'Client/Demo.h').write_bytes(b'class Demo { public: int Run(); };')
            (root / 'Client/Demo.cpp').write_bytes(b'int Demo::Run() { return 7; }')
            (root / 'Client/Unrelated.cpp').write_bytes(b'// Windows punctuation: \x97\r\n')
            projection = SLICE.Projection(root)
            header, source = projection.project('Client/Demo.h', 'Demo', ['Run'], 'Client/Demo.cpp')
            self.assertIn('int Demo::Run() { return 7; }', source)
            self.assertEqual({record['file'] for record in projection.records},
                             {'Client/Demo.h', 'Client/Demo.cpp'})

    def test_selected_mixed_encoding_and_crlf_preserve_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Client').mkdir()
            member = b'int Run() {\r\n return "\x97"[0];\r\n }'
            (root / 'Client/Demo.h').write_bytes(b'class Demo { public: ' + member + b' };')
            (root / 'Client/Demo.cpp').write_bytes(b'int Demo::Other() { return 0; }\r\n')
            projection = SLICE.Projection(root)
            header, source = projection.project('Client/Demo.h', 'Demo', ['Run'], 'Client/Demo.cpp')
            output = root / 'production.inc'
            SLICE.write_source(output, header + source)
            self.assertIn(member, output.read_bytes())
            self.assertEqual(projection.records[0]['sha256'], hashlib.sha256(member).hexdigest())

    def test_relocated_mixed_encoding_body_is_not_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Client').mkdir()
            (root / 'Client/Demo.h').write_bytes(b'class Demo { public: int Run(); };')
            body = 'int Demo::Run() {\r\n // UTF-8 שלום and legacy '.encode() + b'\x97\r\n return 19;\r\n }'
            (root / 'Client/Relocated.cpp').write_bytes(body)
            projection = SLICE.Projection(root)
            header, source = projection.project('Client/Demo.h', 'Demo', ['Run'], 'Client/Missing.cpp')
            output = root / 'production.inc'
            SLICE.write_source(output, header + source)
            self.assertIn(body, output.read_bytes())
            self.assertIn({'file': 'Client/Relocated.cpp', 'line': 1,
                           'sha256': hashlib.sha256(body).hexdigest()}, projection.records)

    def test_state_and_nested_state_declarations(self):
        text = 'class Demo { private: struct State { bool active{false}; }; State state; public: void Run(); };'
        names = set().union(*(names for start, end, names in SLICE.members(text, 'Demo')))
        self.assertTrue({'State', 'state', 'Run'}.issubset(names))

    def test_marker_alias_and_constant(self):
        text = 'class Demo { public: using Kind = Shared::Enum; static constexpr Kind RING = Shared::RING; };'
        names = set().union(*(names for start, end, names in SLICE.members(text, 'Demo')))
        self.assertEqual(names, {'Kind', 'RING'})

    def test_constructor_initializer_is_not_free_function(self):
        self.assertEqual(SLICE.definitions('Demo::Demo() :\n    member(nullptr)\n{ unrelated(); }', 'member'), [])

    def test_overloads_and_masked_braces(self):
        text = 'int Demo::Run(int input) { return input; }\nint Demo::Run() { const char* value = "}"; return 1; }'
        self.assertEqual(len(SLICE.definitions(text, 'Demo::Run')), 2)

    def test_member_initializers_and_helpers_come_from_production(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Client').mkdir()
            (root / 'Client/Demo.h').write_text('class Demo { bool active{false}; public: bool Run() const; };')
            (root / 'Client/Demo.cpp').write_text('static bool Resolve(bool enabled) { return enabled; }\n'
                                                 'bool Demo::Run() const { return Resolve(active); }')
            projection = SLICE.Projection(root)
            header, source = projection.project('Client/Demo.h', 'Demo', ['Run'], 'Client/Demo.cpp')
            self.assertIn('bool active{false};', header)
            self.assertIn('static bool Resolve(bool enabled) { return enabled; }', source)
            self.assertIn('bool Demo::Run() const { return Resolve(active); }', source)
            self.assertEqual(len(projection.records), 4)


if __name__ == '__main__':
    unittest.main()
