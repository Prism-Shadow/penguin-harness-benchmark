import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { load } from '../support/load.mjs';

const { FileCache } = await load('packages/transformers/src/transformers.js');
const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'file-cache-contract-'));
try {
    const cache = new FileCache(directory);
    assert.equal(await cache.match('missing'), undefined);
    for (const size of [513, 131072]) {
        const left = 'L'.repeat(size);
        const right = 'R'.repeat(size + 7);
        await Promise.all([cache.put('same.bin', new Response(left)), cache.put('same.bin', new Response(right))]);
        const response = await cache.match('same.bin');
        assert.equal(response.exists, true);
        const value = await response.text();
        assert.ok(value === left || value === right, 'one complete concurrent body must survive');
        assert.deepEqual(await fs.readdir(directory), ['same.bin']);
    }
    await cache.put('nested/other.bin', new Response('independent key'));
    assert.equal(await (await cache.match('nested/other.bin')).text(), 'independent key');
    await cache.put('stable.bin', new Response('old complete value'));
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    const slow = cache.put('slow.bin', new Response(new ReadableStream({
        async start(controller) {
            controller.enqueue(new TextEncoder().encode('slow-'));
            await gate;
            controller.enqueue(new TextEncoder().encode('complete'));
            controller.close();
        },
    })));
    const failure = new Error('injected download failure');
    let reads = 0;
    const broken = new Response(new ReadableStream({
        pull(controller) {
            if (reads++ === 0) controller.enqueue(new Uint8Array([1, 2, 3]));
            else controller.error(failure);
        },
    }));
    try {
        await assert.rejects(cache.put('stable.bin', broken), (error) => error === failure);
        assert.equal(await (await cache.match('stable.bin')).text(), 'old complete value');
    } finally {
        release();
        await slow;
    }
    assert.equal(await (await cache.match('slow.bin')).text(), 'slow-complete');
    const immediateFailure = new Error('failure before first byte');
    await assert.rejects(cache.put('absent.bin', new Response(new ReadableStream({
        start(controller) { controller.error(immediateFailure); },
    }))), (error) => error === immediateFailure);
    // Give the filesystem boundary a turn to expose writes still queued after rejection.
    await new Promise((resolve) => setTimeout(resolve, 30));
    assert.equal(await cache.match('absent.bin'), undefined);
    assert.equal((await fs.readdir(directory)).some((name) => name.includes('.tmp.')), false);
    await cache.put('stable.bin', new Response('recovered'));
    assert.equal(await (await cache.match('stable.bin')).text(), 'recovered');
    await cache.put('empty.bin', new Response(null));
    assert.equal((await (await cache.match('empty.bin')).arrayBuffer()).byteLength, 0);
    assert.equal(await cache.delete('same.bin'), true);
    assert.equal(await cache.match('same.bin'), undefined);
    assert.equal(await cache.delete('same.bin'), false);
} finally {
    await fs.rm(directory, { recursive: true, force: true });
}
