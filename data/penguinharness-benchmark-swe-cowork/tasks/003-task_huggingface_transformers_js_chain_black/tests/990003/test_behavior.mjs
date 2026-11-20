import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        const { env } = await load('packages/transformers/src/env.js');
assert.equal(typeof env.version, 'string');
assert.equal(typeof env.allowRemoteModels, 'boolean');

const { api, encoderBehavior } = await import('../support/inference.mjs');
await encoderBehavior(api.AutoModel, {model_type: 'bert', hidden_size: 8, num_hidden_layers: 1, num_attention_heads: 1}, 'input_ids', 'last_hidden_state');

await import("../support/native-model.mjs");
