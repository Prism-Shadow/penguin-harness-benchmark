import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const models = await load('packages/transformers/src/transformers.js').catch(() => null);
assert.ok(models, 'the public package entry must resolve');
assert.equal(typeof models.ASTModel, 'function');
assert.equal(typeof models.ASTForAudioClassification, 'function');

const { api, encoderBehavior } = await import('../support/inference.mjs');
await encoderBehavior(api.AutoModelForAudioClassification, {model_type: 'audio-spectrogram-transformer'}, 'input_values', 'logits', 'ASTForAudioClassification');
await encoderBehavior(api.AutoModel, {model_type: 'audio-spectrogram-transformer'}, 'input_values', 'last_hidden_state', 'ASTModel');
