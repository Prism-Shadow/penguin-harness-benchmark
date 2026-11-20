import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        const pipelines = await load('packages/transformers/src/transformers.js');
assert.equal(typeof pipelines.pipeline, 'function');
assert.equal(typeof pipelines.TextGenerationPipeline, 'function');

await import('../support/pipeline-generation.mjs');
