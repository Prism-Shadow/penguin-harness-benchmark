import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ModuleExportsTests(unittest.TestCase):
    def test_named_tokens_survive_default_exports(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node runtime unavailable')
        helper = Path(__file__).parent / 'environment/module_exports.mjs'
        with tempfile.TemporaryDirectory(dir=os.environ.get('TEST_TMPDIR')) as directory:
            root = Path(directory)
            (root / 'connection.mjs').write_text(
                'export const ICdpApi = Symbol("ICdpApi");\n'
                'export default class Connection {}\n')
            (root / 'dap.cjs').write_text(
                'module.exports = { IDapApi: Symbol("IDapApi"), default: class Connection {} };\n')
            (root / 'plain.mjs').write_text('export const FS = Symbol("FS");\n')
            script = f'''
import assert from 'node:assert/strict';
import {{ exportsOf }} from {json.dumps(helper.resolve().as_uri())};
const cdp = await import('./connection.mjs');
const dap = await import('./dap.cjs');
const plain = await import('./plain.mjs');
assert.equal(exportsOf(cdp).ICdpApi, cdp.ICdpApi);
assert.equal(exportsOf(cdp).default, cdp.default);
assert.equal(exportsOf(dap).IDapApi, dap.default.IDapApi);
assert.equal(exportsOf(plain).FS, plain.FS);
const other = Symbol('other');
assert.equal(exportsOf({{ ...cdp, default: {{ ICdpApi: other }} }}).ICdpApi, cdp.ICdpApi);
assert.equal(exportsOf(cdp).nonexistent, undefined);
assert.equal((cdp.default || cdp).ICdpApi, undefined);
console.log('PASS ESM/default, CommonJS, named-only, collision and missing-token controls');
'''
            (root / 'check.mjs').write_text(script)
            result = subprocess.run([node, str(root / 'check.mjs')], text=True,
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())
