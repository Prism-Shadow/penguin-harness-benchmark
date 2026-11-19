import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('production_slice', ROOT / 'tests/production_slice.py')
SLICE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SLICE)


class ProductionSliceTests(unittest.TestCase):
    def test_comments_strings_and_nested_blocks(self):
        source = 'int Demo::Run() { const char* value = "}\\\"{"; /* } */ if (true) { return 1; } }\n'
        start, end = SLICE.definition(source, 'Demo::Run')
        self.assertEqual(source[start:end], source.rstrip())

    def test_raw_string(self):
        source = 'auto Demo::Run() -> const char* { return R"tag( { } " )tag"; }'
        start, end = SLICE.definition(source, 'Demo::Run')
        self.assertEqual(source[start:end], source)

    def test_declaration_and_call_are_not_definition(self):
        source = 'void Demo::Run();\nvoid Caller() { Demo::Run(); }\nvoid Demo::Run() {}'
        start, end = SLICE.definition(source, 'Demo::Run')
        self.assertEqual(source[start:end], 'void Demo::Run() {}')

    def test_ambiguity_fails_closed(self):
        with self.assertRaises(ValueError):
            SLICE.definition('void Demo::Run() {}\nvoid Demo::Run() {}', 'Demo::Run')

    def test_destructor_not_free_helper(self):
        with self.assertRaises(ValueError):
            SLICE.definition('Demo::~Demo() {}', 'Demo')

    def test_multiline_return_type_preserved(self):
        source = '#include "api.h"\n// helper\nnamespace API {\n[[nodiscard]]\nunsigned short\nResolve(int model) { return model; }\n}\n'
        start, end = SLICE.definition(source, 'Resolve')
        self.assertEqual(source[start:end], '[[nodiscard]]\nunsigned short\nResolve(int model) { return model; }')


if __name__ == '__main__':
    unittest.main()
