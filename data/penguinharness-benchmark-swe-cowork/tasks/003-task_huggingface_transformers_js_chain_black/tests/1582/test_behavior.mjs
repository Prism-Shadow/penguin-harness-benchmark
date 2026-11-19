import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';
import { ocrConfig } from '../support/ocr-config.mjs';

const { AutoModelForImageTextToText, PreTrainedModel, Tensor, DynamicCache, GlmOcrForConditionalGeneration, LightOnOcrForConditionalGeneration } =
    await load('packages/transformers/src/transformers.js');
const originalLoader = PreTrainedModel.from_pretrained;
PreTrainedModel.from_pretrained = async function (_name, options) {
    return new this(options.config, {}, {});
};
let model;
try {
    model = await AutoModelForImageTextToText.from_pretrained('offline/ocr', {
        config: structuredClone(ocrConfig),
        local_files_only: true,
    });
    assert.equal(model.constructor, GlmOcrForConditionalGeneration);
    const lighton = await AutoModelForImageTextToText.from_pretrained('offline/lighton', {config: {...structuredClone(ocrConfig), model_type:'lighton_ocr', text_config:{...ocrConfig.text_config,model_type:'qwen2'}}, local_files_only:true});
    assert.equal(lighton.constructor, LightOnOcrForConditionalGeneration);
    await lighton.dispose();
    await assert.rejects(AutoModelForImageTextToText.from_pretrained('offline/unknown', {
        config: { model_type: '__unknown_ocr__' }, local_files_only: true,
    }), /Unsupported model type/);
} finally {
    PreTrainedModel.from_pretrained = originalLoader;
}

const tensor = (values, dims) => new Tensor('int64', BigInt64Array.from(values, BigInt), dims);
const cacheAt = (length, batch) => new DynamicCache({
    'past_key_values.0.key': new Tensor('float32', new Float32Array(batch * length), [batch, 1, length, 1]),
});
function prompt(segments, merge, imageToken) {
    const ids = [];
    const axes = [[], [], []];
    const grids = [];
    let position = 0;
    for (const segment of segments) {
        if (typeof segment === 'number') {
            ids.push(segment);
            for (const axis of axes) axis.push(position);
            position += 1;
        } else {
            const [, height, width] = segment;
            grids.push(segment);
            for (let row = 0; row < height / merge; row += 1) {
                for (let column = 0; column < width / merge; column += 1) {
                    ids.push(imageToken);
                    axes[0].push(position);
                    axes[1].push(position + row);
                    axes[2].push(position + column);
                }
            }
            position += Math.max(height, width) / merge;
        }
    }
    return { ids, axes, grids, position };
}

for (const [merge, imageToken, rows] of [
    [2, 71, [[11, 12, [1, 4, 6], 13]]],
    [2, 97, [[[3, 6, 4], 71, [1, 2, 8], 14]]],
    [2, 71, [[11, [1, 4, 4], 12], [[2, 2, 4], 13]]],
    [3, 103, [[11, [2, 6, 9], 71]]],
]) {
    model.config.vision_config.spatial_merge_size = merge;
    model.config.image_token_id = imageToken;
    const prompts = rows.map((segments) => prompt(segments, merge, imageToken));
    const sequence = Math.max(...prompts.map((item) => item.ids.length)) + 1;
    const padded = prompts.map((item) => {
        const padding = sequence - item.ids.length;
        return {
            ids: [...Array(padding).fill(0), ...item.ids],
            mask: [...Array(padding).fill(0), ...Array(item.ids.length).fill(1)],
            axes: item.axes.map((axis) => [...Array(padding).fill(0), ...axis]),
        };
    });
    const inputIds = tensor(padded.flatMap((item) => item.ids), [rows.length, sequence]);
    const attentionMask = tensor(padded.flatMap((item) => item.mask), [rows.length, sequence]);
    const grids = prompts.flatMap((item) => item.grids);
    const imageGrid = tensor(grids.flat(), [grids.length, 3]);
    const expected = [0, 1, 2].flatMap((axis) => padded.flatMap((item) => item.axes[axis])).map(BigInt);
    const [positions, deltas] = model.get_rope_index(inputIds, imageGrid, null, attentionMask);
    assert.equal(positions.type, 'int64');
    assert.deepEqual(positions.dims, [3, rows.length, sequence]);
    assert.deepEqual(Array.from(positions.data), expected);
    assert.equal(deltas.type, 'int64');
    assert.deepEqual(deltas.dims, [rows.length, 1]);
    assert.deepEqual(Array.from(deltas.data), prompts.map((item) => BigInt(item.position - sequence)));

    const pixels = tensor([8], [1]);
    const prefill = model.prepare_inputs_for_generation(inputIds, {
        input_ids: inputIds, attention_mask: attentionMask, image_grid_thw: imageGrid, pixel_values: pixels,
    }, {});
    assert.deepEqual(Array.from(prefill.position_ids.data), expected);
    assert.deepEqual(Array.from(prefill.rope_deltas.data), Array.from(deltas.data));
    assert.strictEqual(prefill.pixel_values, pixels);
    const nextIds = tensor(Array(rows.length).fill(27), [rows.length, 1]);
    const next = model.prepare_inputs_for_generation(nextIds, {
        input_ids: nextIds,
        attention_mask: tensor(padded.flatMap((item) => [...item.mask, 1]), [rows.length, sequence + 1]),
        past_key_values: cacheAt(sequence, rows.length), rope_deltas: deltas, pixel_values: pixels,
    }, {});
    assert.equal(next.pixel_values, null);
    assert.deepEqual(next.position_ids.dims, [3, rows.length, 1]);
    assert.deepEqual(Array.from(next.position_ids.data),
        [0, 1, 2].flatMap(() => prompts.map((item) => BigInt(item.position))));
    const suffix = model.prepare_inputs_for_generation(inputIds, {
        input_ids: inputIds, attention_mask: attentionMask, image_grid_thw: imageGrid,
        past_key_values: cacheAt(sequence - 1, rows.length), pixel_values: pixels,
    }, {});
    assert.equal(suffix.pixel_values, null);
    assert.deepEqual(suffix.input_ids.dims, [rows.length, 1]);
    assert.deepEqual(suffix.position_ids.dims, [3, rows.length, 1]);
    assert.deepEqual(Array.from(suffix.position_ids.data),
        [0, 1, 2].flatMap((axis) => padded.map((item) => BigInt(item.axes[axis].at(-1)))));
}

const textIds = tensor([1, 2, 3, 4, 5, 6], [2, 3]);
for (const mask of [undefined, tensor(Array(6).fill(1), [2, 3])]) {
    const [positions, deltas] = model.get_rope_index(textIds, null, null, mask);
    assert.deepEqual(Array.from(positions.data), Array(6).fill([0n, 1n, 2n]).flat());
    assert.deepEqual(Array.from(deltas.data), [0n, 0n]);
}
const fresh = model.prepare_inputs_for_generation(textIds, {
    input_ids: textIds, attention_mask: tensor(Array(6).fill(1), [2, 3]),
}, {});
assert.deepEqual(Array.from(fresh.rope_deltas.data), [0n, 0n]);

await import('../support/ocr-generation.mjs');

await import("../support/lighton-generation.mjs");
