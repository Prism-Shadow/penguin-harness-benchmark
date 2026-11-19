import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';
const { env, ModelRegistry } = await load('packages/transformers/src/transformers.js');
env.useCustomCache = true;
env.useFSCache = false;
env.useBrowserCache = false;
env.allowLocalModels = false;
env.allowRemoteModels = false;
const options = {
    config: { model_type: 'bert', architectures: ['BertModel'], num_hidden_layers: 1, num_attention_heads: 1, hidden_size: 8 },
    dtype: 'fp32', include_tokenizer: false, include_processor: false,
};
const cases = ['fp32', 'fp16', 'q8'].map((dtype) => ({...options, dtype}));
cases.push({...options, config:{model_type:'t5',architectures:['T5ForConditionalGeneration'],is_encoder_decoder:true,d_model:8,d_kv:8,num_heads:1,num_layers:1,num_decoder_layers:1}, dtype:{model:'fp16',decoder_model_merged:'q8'}});
cases.push({...options, config:{...(await import('../support/ocr-config.mjs')).ocrConfig,architectures:['GlmOcrForConditionalGeneration']}});
for (const selected of cases) {
    const files = await ModelRegistry.get_model_files('org/boolean-cache', selected);
    for (const missing of [null, ...files]) {
        env.customCache = { match: async (request) => {
            const key = String(request);
            return missing && key.endsWith('/' + missing) ? undefined : new Response('cached');
        }, put: async () => {} };
        const result = await ModelRegistry.is_cached('org/boolean-cache', selected);
        assert.equal(typeof result, 'boolean');
        assert.equal(result, missing === null, `model=${selected.config.model_type}, dtype=${JSON.stringify(selected.dtype)}, missing=${missing}`);
    }
}
env.useCustomCache = false;
assert.equal(await ModelRegistry.is_cached('org/boolean-cache', options), false);
