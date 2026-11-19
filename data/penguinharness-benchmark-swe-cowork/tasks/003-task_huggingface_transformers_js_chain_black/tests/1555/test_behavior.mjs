import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        const { AutoModelForCausalLM } = await load('packages/transformers/src/transformers.js');
assert.equal(typeof AutoModelForCausalLM.supports, 'function');
assert.equal(AutoModelForCausalLM.supports('gpt2'), true);
assert.equal(AutoModelForCausalLM.supports('__missing_model_type__'), false);
