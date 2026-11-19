import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';
import { browserStorage, digest, eventually } from '../support/cos-browser.mjs';

const { CrossOriginStorage } = await load('packages/transformers/src/transformers.js');
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} });
assert.equal(CrossOriginStorage.isAvailable(), false);
const browser = browserStorage();
const cache = new CrossOriginStorage();
assert.equal(CrossOriginStorage.isAvailable(), true);
for (const [index, bytes] of [new Uint8Array([255, 0, 7]), new TextEncoder().encode('跨源 café'), new Uint8Array()].entries()) {
    const request = `https://example.invalid/blob-${index}`;
    const hash = digest(bytes);
    assert.equal(await cache.match(request), undefined);
    await cache.put(request, new Response(bytes));
    await eventually(() => browser.mappings.has(request), 'unknown hash must eventually establish a URL mapping');
    assert.equal(browser.mappings.get(request), hash);
    const response = await cache.match(request);
    assert.ok(response instanceof Response);
    assert.equal(response.headers.get('content-length'), String(bytes.length));
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
    const lifecycle = browser.events.filter((event) => event[1] === hash && ['write', 'close'].includes(event[0]));
    assert.deepEqual(lifecycle.map((event) => event[0]), ['write', 'close']);
    assert.equal(await cache.delete(request), true);
    assert.equal(await cache.match(request), undefined);
    assert.equal(await cache.delete(request), false);
}
// The known-hash branch must await both write and close.
const request = 'https://example.invalid/known';
const bytes = new TextEncoder().encode('known body');
const hash = digest(bytes);
browser.mappings.set(request, hash);
await cache.put(request, new Response(bytes));
assert.equal(await (await cache.match(request)).text(), 'known body');
for (const stage of ['failWrite', 'failClose']) {
    browser[stage] = true;
    await assert.rejects(cache.put(request, new Response(bytes)), /injected COS/);
    browser[stage] = false;
    await cache.put(request, new Response(bytes));
    assert.equal(await (await cache.match(request)).text(), 'known body');
}

// Updating a URL must preserve the content-addressed invariant.
const replacement = new TextEncoder().encode('changed URL body 世界');
await cache.put(request, new Response(replacement));
assert.equal(browser.mappings.get(request), digest(replacement));
assert.deepEqual(new Uint8Array(await (await cache.match(request)).arrayBuffer()), replacement);
browser.failWrite = true;
try { await assert.rejects(cache.put(request, new Response('must not replace complete entry')), /injected COS write failure/); }
finally { browser.failWrite = false; }
assert.equal(browser.mappings.get(request), digest(replacement));
assert.deepEqual(new Uint8Array(await (await cache.match(request)).arrayBuffer()), replacement);


// Failure at either asynchronous boundary must remain observable and retryable.
const cryptoDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
const warnings = [];
const warn = console.warn, error = console.error;
console.warn = console.error = (...args) => warnings.push(args.map(String).join(' '));
try {
    for (const stage of ['hash', 'write', 'close']) {
        const failedRequest = `https://example.invalid/failure-${stage}`;
        const before = warnings.length;
        if (stage === 'hash') Object.defineProperty(globalThis, 'crypto', {configurable: true, value: {
            subtle: {digest: async () => {throw new Error('injected COS hash failure');}},
        }});
        else browser[stage === 'write' ? 'failWrite' : 'failClose'] = true;
        await cache.put(failedRequest, new Response('retry body')).catch((e) => warnings.push(String(e)));
        await eventually(() => warnings.length > before, 'background failures must be observable');
        assert.ok(warnings.slice(before).some((x) => x.includes(`injected COS ${stage} failure`)));
        assert.equal(browser.mappings.has(failedRequest), false, 'a failed blob must never publish a mapping');
        if (cryptoDescriptor) Object.defineProperty(globalThis, 'crypto', cryptoDescriptor);
        browser.failWrite = browser.failClose = false;
        await cache.put(failedRequest, new Response('retry body'));
        await eventually(() => browser.mappings.has(failedRequest), 'a failed write can be retried');
        assert.equal(await (await cache.match(failedRequest)).text(), 'retry body');
    }
} finally {
    console.warn = warn; console.error = error;
    if (cryptoDescriptor) Object.defineProperty(globalThis, 'crypto', cryptoDescriptor);
    browser.failWrite = browser.failClose = false;
}

// A temporary Cache API failure must not permanently poison the cache instance.
const browserOpen = globalThis.caches.open;
const retryWarnings = [];
const savedWarn = console.warn, savedError = console.error;
console.warn = console.error = (...args) => retryWarnings.push(args.map(String).join(' '));
try {
    for (const stage of ['open', 'mapping']) {
        let unavailable = true;
        const transient = new CrossOriginStorage();
        const url = `https://example.invalid/transient-${stage}`;
        globalThis.caches.open = async (...args) => {
            if (stage === 'open' && unavailable) throw new Error('injected Cache API open failure');
            const mappingCache = await browserOpen(...args);
            return { ...mappingCache, put: async (...values) => {
                if (stage === 'mapping' && unavailable) throw new Error('injected Cache API mapping failure');
                return mappingCache.put(...values);
            } };
        };
        const before = retryWarnings.length;
        await transient.put(url, new Response('mapping retry')).catch((e) => retryWarnings.push(String(e)));
        await eventually(() => retryWarnings.length > before, 'mapping failures remain diagnosable');
        assert.ok(retryWarnings.slice(before).some((x) => x.includes(`injected Cache API ${stage} failure`)));
        assert.equal(browser.mappings.has(url), false);
        unavailable = false;
        await transient.put(url, new Response('mapping retry'));
        await eventually(() => browser.mappings.has(url), 'the same cache instance recovers after a transient mapping failure');
        assert.equal(await (await transient.match(url)).text(), 'mapping retry');
    }
} finally {
    globalThis.caches.open = browserOpen;
    console.warn = savedWarn; console.error = savedError;
}
