import assert from 'node:assert/strict';
import { load } from './load.mjs';
import { createRequire } from 'node:module';
import path from 'node:path';
const require = createRequire(path.join(process.env.REPO_DIR_OVERRIDE || process.env.REPO_DIR || process.cwd(), 'packages/transformers/package.json'));
const { Tensor: NativeTensor } = require('onnxruntime-node');
export const api = await load('packages/transformers/src/transformers.js');
export const tensor = (type, values, dims) => new api.Tensor(type, values, dims);
export const i64 = (values, dims) => tensor('int64', BigInt64Array.from(values, BigInt), dims);
export const ort = (type, values, dims) => new NativeTensor(type, values, dims);

// Replace only weight/session construction. AutoConfig, AutoModel selection,
// model construction, callable forward, generate, cache advancement and disposal
// execute unchanged production code. No helper name or inheritance is asserted.
export async function withModel(auto, config, sessions, action) {
    const original = api.PreTrainedModel.from_pretrained;
    let model;
    api.PreTrainedModel.from_pretrained = async function (_name, options) {
        return new this(options.config, sessions, {});
    };
    try {
        model = await auto.from_pretrained('offline/behavior', { config: structuredClone(config), local_files_only: true });
    } finally {
        api.PreTrainedModel.from_pretrained = original;
    }
    try { return await action(model); }
    finally { await model.dispose(); }
}
export const causalConfig = (model_type) => ({
    model_type, num_hidden_layers: 1, num_attention_heads: 1, num_key_value_heads: 1,
    hidden_size: 8, head_dim: 8, qk_head_dim: 8, vocab_size: 128,
    n_layer: 1, n_head: 1, n_embd: 8,
    layer_types: [model_type === 'nemotron_h' ? 'attention' : 'full_attention'],
    linear_num_value_heads: 1, linear_num_key_heads: 1, linear_key_head_dim: 8,
    linear_value_head_dim: 8, linear_conv_kernel_dim: 3,
});
export function causalSession() {
    const runs = [];
    let releases = 0;
    let fail = false;
    const session = {
        config: { kv_cache_dtype: 'float32' },
        inputNames: ['input_ids', 'attention_mask', 'past_key_values.0.key', 'past_key_values.0.value'],
        async run(feeds) {
            if (fail) { fail = false; throw new Error('injected inference failure'); }
            const ids = feeds.input_ids;
            const past = feeds['past_key_values.0.key'];
            const [batch, length] = ids.dims;
            const previous = past.dims[2];
            assert.equal(feeds.attention_mask.dims[1], previous + length);
            if (previous) assert.ok(Array.from(past.data).every((x) => x === previous), 'previous cache data must be reused');
            const logits = new Float32Array(batch * length * 128).fill(-100);
            for (let i = 0; i < ids.data.length; ++i) logits[i * 128 + (Number(ids.data[i]) + 1) % 128] = 100;
            const total = previous + length;
            const shape = [batch, 1, total, 8];
            runs.push({ ids: Array.from(ids.data), previous, length });
            return {
                logits: ort('float32', logits, [batch, length, 128]),
                'present.0.key': ort('float32', new Float32Array(batch * total * 8).fill(total), shape),
                'present.0.value': ort('float32', new Float32Array(batch * total * 8).fill(total), shape),
            };
        },
        async release() { releases += 1; },
    };
    return { session, runs, get releases() { return releases; }, set fail(value) { fail = value; } };
}
export async function causalBehavior(modelType) {
    const boundary = causalSession();
    await withModel(api.AutoModelForCausalLM, causalConfig(modelType), { model: boundary.session }, async (model) => {
        const publicNames = {afmoe:'AfmoeForCausalLM', qwen2_moe:'Qwen2MoeForCausalLM', qwen3_next:'Qwen3NextForCausalLM',
            olmo_hybrid:'OlmoHybridForCausalLM', nemotron_h:'NemotronHForCausalLM', deepseek_v3:'DeepseekV3ForCausalLM',
            mistral4:'Mistral4ForCausalLM', glm_moe_dsa:'GlmMoeDsaForCausalLM', solar_open:'SolarOpenForCausalLM',gpt2:'GPT2LMHeadModel'};
        assert.equal(model.constructor, api[publicNames[modelType]], 'AutoModel selects the declared public class');
        for (const prompt of [[3, 9], [17, 21]]) {
            const start = boundary.runs.length;
            const result = await model.generate({ input_ids: i64(prompt, [1, 2]), attention_mask: i64([1, 1], [1, 2]), max_new_tokens: 3, do_sample: false });
            assert.deepEqual(result.tolist(), [[...prompt, prompt[1] + 1, prompt[1] + 2, prompt[1] + 3].map(BigInt)]);
            assert.deepEqual(boundary.runs.slice(start).map((x) => [x.previous, x.length]), [[0, 2], [2, 1], [3, 1]]);
        }
        boundary.fail = true;
        await assert.rejects(model.generate({ input_ids: i64([4, 6], [1, 2]), attention_mask: i64([1, 1], [1, 2]), max_new_tokens: 2 }), /injected inference failure/);
        const recovered = await model.generate({ input_ids: i64([1, 2], [1, 2]), attention_mask: i64([1, 1], [1, 2]), max_new_tokens: 2 });
        assert.deepEqual(recovered.tolist(), [[1n, 2n, 3n, 4n]]);
    });
    assert.equal(boundary.releases, 1, 'session resources are released');
}
export async function encoderBehavior(auto, config, inputName = 'input_ids', outputName = 'logits', publicName = null) {
    let runs = 0;
    let releases = 0;
    const session = {
        inputNames: [inputName],
        async run(feeds) {
            runs += 1;
            const input = feeds[inputName];
            return { [outputName]: ort('float32', Float32Array.from(input.data, (x) => Number(x) * 2 + 1), input.dims) };
        },
        async release() { releases += 1; },
    };
    await withModel(auto, config, { model: session }, async (model) => {
        if (publicName) assert.equal(model.constructor, api[publicName]);
        for (const values of [[1, 7, 3], [8, 2, 5]]) {
            const input = inputName === 'input_ids' ? i64(values, [1, 3]) : tensor('float32', new Float32Array(values), [1, 3]);
            const result = await model({ [inputName]: input });
            assert.deepEqual(Array.from(result[outputName].data), values.map((x) => x * 2 + 1));
            assert.deepEqual(result[outputName].dims, [1, 3]);
        }
        await assert.rejects(model({}), /Missing|missing/);
    });
    assert.equal(runs, 2);
    assert.equal(releases, 1);
}
