import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
export function runScript(url, args = []) {
    const nonce = randomUUID();
    const result = spawnSync(process.execPath, [fileURLToPath(new URL('./script-runner.mjs', import.meta.url)), fileURLToPath(url), ...args], {
        env: {...process.env, COWORK_SCRIPT_NONCE: nonce}, encoding:'utf8', timeout:60000,
    });
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    if (result.error) throw result.error;
    assert.equal(result.status, 0, 'child behavior run must succeed');
    assert.equal(result.stdout.split(`COWORK_SCRIPT_DONE=${nonce}\n`).length, 2, 'child assertions must complete; an early successful exit is not a pass');
}
