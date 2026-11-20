import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        let receiver;
globalThis.fetch = function () {
    receiver = this;
    return Promise.resolve(new Response('receiver-ok', { status: 200 }));
};
const { env } = await load('packages/transformers/src/env.js');
assert.equal(typeof env.fetch, 'function');
const response = await env.fetch('https://example.invalid/receiver');
assert.equal(await response.text(), 'receiver-ok');
assert.strictEqual(receiver, globalThis);
