import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const { env } = await load('packages/transformers/src/env.js');
const { getFile } = await load('packages/transformers/src/utils/hub.js');
const previous = env.fetch;
try {
    for (const status of [200, 206, 404]) {
        const response = new Response(`body-${status}`, { status, headers: { 'x-probe': `${status}` } });
        let calls = 0;
        env.fetch = async (url) => {
            calls += 1;
            assert.equal(url, `https://example.invalid/resource-${status}`);
            return response;
        };
        const result = await getFile(`https://example.invalid/resource-${status}`);
        assert.strictEqual(result, response);
        assert.equal(result.bodyUsed, false);
        assert.equal(await result.text(), `body-${status}`);
        assert.equal(calls, 1);
    }
    const failure = new Error('transport failure');
    env.fetch = async () => { throw failure; };
    await assert.rejects(getFile('https://example.invalid/failure'), (error) => error === failure);
} finally {
    env.fetch = previous;
}
