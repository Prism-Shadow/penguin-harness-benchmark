import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const { DynamicCache, Tensor } = await load('packages/transformers/src/transformers.js');
assert.equal(typeof DynamicCache, 'function');
const cache = new DynamicCache({
    'past_key_values.0.key': new Tensor('float32', new Float32Array(3), [1, 1, 3, 1]),
});
assert.equal(cache.get_seq_length(), 3);
assert.throws(() => new DynamicCache({ invalid: 1 }), /Expected a Tensor/);
