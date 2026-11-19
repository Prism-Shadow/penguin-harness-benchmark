import assert from 'node:assert/strict';
import { api, ort, i64, tensor, withModel } from './inference.mjs';
import { ocrConfig } from './ocr-config.mjs';
// The checkpoint chooses its established image processor; no new private OCR class is required.
const previousEnv = {useCustomCache: api.env.useCustomCache, customCache: api.env.customCache, useFSCache: api.env.useFSCache, useBrowserCache: api.env.useBrowserCache};
const processedCases = [];
let processed;
try {
    api.env.useCustomCache = true;
    api.env.useFSCache = false;
    api.env.useBrowserCache = false;
    api.env.customCache = {match: async () => new Response(JSON.stringify({
        image_processor_type: 'Qwen2VLImageProcessor', do_resize: false, do_rescale: false,
        do_normalize: false, patch_size: 2, temporal_patch_size: 1, merge_size: 2,
    })), put: async () => {}};
    const processor = await api.AutoImageProcessor.from_pretrained('offline/ocr-processor');
    for (const value of [90, 17]) {
        const result = await processor(new api.RawImage(new Uint8ClampedArray(8*8*3).fill(value), 8, 8, 3));
        assert.deepEqual(result.image_grid_thw.tolist(), [[1n,4n,4n]]);
        assert.deepEqual(result.pixel_values.dims, [16,12]);
        assert.ok(Array.from(result.pixel_values.data).every((x) => x === value));
        processedCases.push(result);
    }
    processed = processedCases[0];
} finally { Object.assign(api.env, previousEnv); }
let visionCalls = 0;
let expectedImageValue = 90;
let releases = 0;
let failVision = false;
const steps = [];
const session = (inputNames, run) => ({ inputNames, config: { kv_cache_dtype: 'float32' }, run, async release() { releases += 1; } });
const sessions = {
    embed_tokens: session(['input_ids'], async ({input_ids}) => {
        const values = Float32Array.from({length: input_ids.data.length * 8}, (_, i) => Number(input_ids.data[Math.floor(i / 8)]) + i % 8);
        return { inputs_embeds: ort('float32', values, [...input_ids.dims, 8]) };
    }),
    vision_encoder: session(['pixel_values', 'image_grid_thw'], async ({pixel_values, image_grid_thw}) => {
        visionCalls += 1;
        if (failVision) { failVision = false; throw new Error('injected vision failure'); }
        assert.deepEqual(Array.from(image_grid_thw.data), [1n, 4n, 4n]);
        return { image_features: ort('float32', Float32Array.from({length: 32}, (_, i) => Number(pixel_values.data[0]) + i), [4, 8]) };
    }),
    decoder_model_merged: session(['inputs_embeds', 'attention_mask', 'position_ids', 'past_key_values.0.key', 'past_key_values.0.value'], async (feeds) => {
        const { inputs_embeds: embeds, position_ids: positions, attention_mask: mask } = feeds;
        const previous = feeds['past_key_values.0.key'].dims[2];
        const length = embeds.dims[1];
        assert.equal(mask.dims[1], previous + length);
        const values = Array.from(embeds.data);
        if (!previous && length === 6) {
            assert.deepEqual(values.slice(8, 40), Array.from({length: 32}, (_, i) => expectedImageValue + i), 'vision features replace every image placeholder');
            assert.deepEqual(values.slice(0, 8), [11,12,13,14,15,16,17,18]);
            assert.deepEqual(values.slice(40), [12,13,14,15,16,17,18,19]);
            assert.deepEqual(Array.from(positions.data), [0n,1n,1n,1n,1n,3n, 0n,1n,1n,2n,2n,3n, 0n,1n,2n,1n,2n,3n]);
        } else if (previous) {
            assert.equal(length, 1);
            assert.deepEqual(Array.from(positions.data), Array(3).fill(BigInt(previous - 2)));
            assert.ok(Array.from(feeds['past_key_values.0.key'].data).every((x) => x === previous));
        }
        const next = Math.round(values.at(-8)) + 1;
        const logits = new Float32Array(length * 128).fill(-100);
        logits[(length - 1) * 128 + next] = 100;
        const total = previous + length;
        steps.push([previous, length]);
        return {
            logits: ort('float32', logits, [1, length, 128]),
            'present.0.key': ort('float32', new Float32Array(total * 8).fill(total), [1, 1, total, 8]),
            'present.0.value': ort('float32', new Float32Array(total * 8).fill(total), [1, 1, total, 8]),
        };
    }),
};
await withModel(api.AutoModelForImageTextToText, ocrConfig, sessions, async (model) => {
    const inputs = () => ({
        input_ids: i64([11,71,71,71,71,12], [1,6]), attention_mask: i64([1,1,1,1,1,1], [1,6]),
        image_grid_thw: processed.image_grid_thw, pixel_values: processed.pixel_values,
        max_new_tokens: 3, do_sample: false,
    });
    const output = await model.generate(inputs());
    assert.deepEqual(output.tolist(), [[11n,71n,71n,71n,71n,12n,13n,14n,15n]]);
    assert.deepEqual(steps, [[0,6],[6,1],[7,1]]);
    assert.equal(visionCalls, 1, 'continuation must not rerun the vision encoder');
    processed = processedCases[1];
    expectedImageValue = 17;
    assert.deepEqual((await model.generate(inputs())).tolist(), output.tolist());
    assert.equal(visionCalls, 2, 'a new image is processed from its own pixels');
    failVision = true;
    await assert.rejects(model.generate(inputs()), /injected vision failure/);
    const recovered = await model.generate(inputs());
    assert.deepEqual(recovered.tolist(), output.tolist());
    assert.equal(visionCalls, 4);
    // A fresh text-only request has no stale image embeddings or rope delta.
    const text = await model.generate({ input_ids: i64([3,4], [1,2]), attention_mask: i64([1,1], [1,2]), max_new_tokens: 1 });
    assert.deepEqual(text.tolist(), [[3n,4n,5n]]);
    assert.equal(visionCalls, 4);
});
assert.equal(releases, 3);
