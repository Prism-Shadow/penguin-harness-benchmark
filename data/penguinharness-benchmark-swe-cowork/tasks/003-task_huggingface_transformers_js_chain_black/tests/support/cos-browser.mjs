import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

// Only the browser's external storage boundary is replaced. The production cache
// owns hashing, mapping, write ordering, and read/delete operations.
export function browserStorage() {
    const mappings = new Map();
    const blobs = new Map();
    const events = [];
    let failWrite = false;
    let failClose = false;
    const key = (request) => typeof request === 'string' ? request : request.url;
    globalThis.caches = { open: async () => ({
        async match(request) { return mappings.has(key(request)) ? new Response(mappings.get(key(request))) : undefined; },
        async put(request, response) { mappings.set(key(request), await response.text()); events.push(['map', key(request)]); },
        async delete(request) { return mappings.delete(key(request)); },
    }) };
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { crossOriginStorage: {
        async requestFileHandles(descriptors, options) {
            return descriptors.map(({ algorithm, value }) => {
                events.push(['handle', value, options?.create === true]);
                assert.equal(algorithm, 'SHA-256');
                assert.match(value, /^[0-9a-f]{64}$/);
                return {
                    async createWritable() {
                        assert.equal(options?.create, true);
                        let pending;
                        return {
                            async write(blob) {
                                events.push(['write', value]);
                                if (failWrite) throw new Error('injected COS write failure');
                                assert.equal(createHash('sha256').update(new Uint8Array(await blob.arrayBuffer())).digest('hex'), value);
                                pending = blob;
                            },
                            async close() {
                                events.push(['close', value]);
                                if (failClose) throw new Error('injected COS close failure');
                                assert.ok(pending, 'write must complete before close');
                                blobs.set(value, pending);
                            },
                            async abort() { events.push(['abort', value]); pending = undefined; },
                        };
                    },
                    async getFile() {
                        if (!blobs.has(value)) throw new Error('missing blob');
                        return blobs.get(value);
                    },
                };
            });
        },
    } } });
    return { mappings, blobs, events, set failWrite(value) { failWrite = value; }, set failClose(value) { failClose = value; } };
}
export const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
export async function eventually(check, message) {
    const end = Date.now() + 3000;
    do {
        if (await check()) return;
        await new Promise((resolve) => setTimeout(resolve, 5));
    } while (Date.now() < end);
    assert.fail(message);
}
