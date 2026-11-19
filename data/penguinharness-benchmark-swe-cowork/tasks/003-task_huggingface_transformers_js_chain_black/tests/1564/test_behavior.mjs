import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const { env } = await load('packages/transformers/src/env.js');
const { get_file_metadata } = await load('packages/transformers/src/utils/model_registry/get_file_metadata.js');
env.useCustomCache = false;
env.useFSCache = false;
env.useBrowserCache = false;
env.allowLocalModels = false;
env.allowRemoteModels = true;
for (const size of [1, 42, 8197]) {
    let calls = 0;
    env.fetch = async (_url, options) => {
        calls += 1;
        assert.equal(options.cache, 'no-store');
        assert.equal(options.headers.get('Range'), 'bytes=0-0');
        return new Response('x', { status: 206, headers: {
            'Content-Range': `bytes 0-0/${size}`, 'Content-Length': '1', 'Content-Type': 'application/octet-stream',
        } });
    };
    const metadata = await get_file_metadata(`org/range-${size}`, 'config.json');
    assert.equal(metadata.exists, true);
    assert.equal(metadata.size, size);
    assert.equal(calls, 1);
}
env.fetch = async () => new Response('not found', { status: 404 });
assert.equal((await get_file_metadata('org/missing', 'config.json')).exists, false);
