import assert from 'node:assert/strict';
import { load } from './load.mjs';
// Exercise the browser's serialized load/run queues with the real native CPU
// provider. This isolates scheduling from graphics hardware availability.
globalThis.self = globalThis;
globalThis.window = {document:{}};
const api = await load('packages/transformers/src/transformers.js');
const {apis} = await load('packages/transformers/src/env.js');
assert.equal(apis.IS_WEB_ENV, true);
// The hybrid environment selects browser scheduling while retaining the real
// native CPU provider and filesystem fixture. Explicitly enable local models;
// a normal browser defaults to remote loading.
api.env.allowLocalModels = true;
const {nativeModelBehavior} = await import('./native-model.mjs');
await nativeModelBehavior(api, {failureRecovery:true});
console.log('browser queue recovery after real ORT load/inference failures: passed');
