import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        const { TextGenerationPipeline } = await load('packages/transformers/src/transformers.js');
assert.equal(typeof TextGenerationPipeline, 'function');

await import('../support/pipeline-generation.mjs');
