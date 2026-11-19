import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';
import { browserStorage, digest, eventually } from '../support/cos-browser.mjs';
const { CrossOriginStorage, env } = await load('packages/transformers/src/transformers.js');
const browser = browserStorage();
const cache = new CrossOriginStorage();
for (const body of ['abc', '世界', '']) {
    const request = `https://example.invalid/read-${encodeURIComponent(body)}`;
    await cache.put(request, new Response(body));
    await eventually(async () => !!(await cache.match(request)), 'put/match readback');
    const response = await cache.match(request);
    assert.equal(response.headers.get('content-length'), String(Buffer.byteLength(body)));
    assert.equal(await response.text(), body);
}
for (const value of ['a'.repeat(63), 'a'.repeat(65), 'A'.repeat(64), 'g'.repeat(64), 'a'.repeat(64) + '\n']) {
    const request = 'https://example.invalid/invalid';
    browser.mappings.set(request, value);
    const before = browser.events.length;
    assert.equal(await cache.match(request), undefined);
    assert.equal(browser.events.length, before, 'invalid mapped hash must not reach the COS API');
}
const request = 'https://example.invalid/null-body';
await cache.put(request, new Response(null));
await eventually(async () => !!(await cache.match(request)), 'a null Response body represents an empty blob');
assert.equal(browser.mappings.get(request), digest(new Uint8Array()));
assert.equal((await (await cache.match(request)).arrayBuffer()).byteLength, 0);
// LFS pointer lookup and the fallback hash path use the same real blob store.
const originalFetch = globalThis.fetch;
const originalOverride = env.fetch;
globalThis.fetch = async () => { throw new Error('LFS lookup bypassed env.fetch'); };
try {
    const body = new TextEncoder().encode('LFS content');
    const correct = digest(body);
    for (const [index, pointerHash] of [correct, 'a'.repeat(63), 'a'.repeat(65), 'A'.repeat(64)].entries()) {
        let fetched = 0;
        const url = `https://example.invalid/model/resolve/main/blob-${index}`;
        env.fetch = async (pointerUrl) => {
            assert.equal(pointerUrl, url.replace('/resolve/', '/raw/'));
            fetched++;
            return new Response(`version https://git-lfs.github.com/spec/v1\noid sha256:${pointerHash}\nsize ${body.length}\n`);
        };
        await cache.put(url, new Response(body));
        await eventually(() => browser.mappings.get(url) === correct, 'invalid LFS digests must fall back to hashing bytes');
        assert.equal(fetched, 1);
        assert.deepEqual(new Uint8Array(await (await cache.match(url)).arrayBuffer()), body);
    }
} finally { globalThis.fetch = originalFetch; env.fetch = originalOverride; }
const fetchBeforeInvalidRead = env.fetch;
try {
    for (const [i, hash] of ['a'.repeat(63), 'a'.repeat(65), 'G'.repeat(64)].entries()) {
        const url = `https://example.invalid/invalid-pointer/resolve/main/${i}`;
        env.fetch = async () => new Response(`oid sha256:${hash}\n`);
        const before = browser.events.filter((event) => event[0] === 'handle').length;
        assert.equal(await cache.match(url), undefined);
        assert.equal(browser.events.filter((event) => event[0] === 'handle').length, before, 'invalid LFS hash cannot request a handle');
        assert.equal(browser.mappings.has(url), false, 'invalid LFS hash cannot become a URL mapping');
    }
} finally { env.fetch = fetchBeforeInvalidRead; }
