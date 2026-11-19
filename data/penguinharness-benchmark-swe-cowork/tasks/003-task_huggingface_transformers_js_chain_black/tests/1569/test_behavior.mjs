import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const module = await load('packages/transformers/src/transformers.js').catch(() => null);
assert.ok(module && typeof module.DynamicCache === 'function');
const { Tensor } = module;
const tensor = new Tensor('float32', new Float32Array([1, 2, 3, 4]), [1, 1, 2, 2]);
const cache = new module.DynamicCache({ 'past_key_values.0.key': tensor });
assert.equal(cache.get_seq_length(), 2);
assert.throws(() => new module.DynamicCache({ invalid: 1 }), /Expected a Tensor/);
