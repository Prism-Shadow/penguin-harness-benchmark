import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';
const { ModelRegistry } = await load('packages/transformers/src/transformers.js');
const encoder = { model_type: 'bert', architectures: ['BertModel'], num_hidden_layers: 1, num_attention_heads: 1, hidden_size: 8 };
for (const [dtype, suffix] of [['fp32',''], ['fp16','_fp16'], ['q8','_quantized'], ['q4','_q4']]) {
    const files = await ModelRegistry.get_model_files('org/model', { config: encoder, dtype });
    assert.deepEqual(files, ['config.json', `onnx/model${suffix}.onnx`]);
}
const seq2seq = { model_type: 't5', architectures: ['T5ForConditionalGeneration'], is_encoder_decoder: true,
    d_model: 8, d_kv: 8, num_heads: 1, num_layers: 1, num_decoder_layers: 1 };
assert.deepEqual(await ModelRegistry.get_model_files('org/seq2seq', {
    config: seq2seq, dtype: { model: 'fp16', decoder_model_merged: 'q8' },
}), ['config.json', 'onnx/encoder_model_fp16.onnx', 'onnx/decoder_model_merged_quantized.onnx', 'generation_config.json']);
const multimodal = { ...(await import('../support/ocr-config.mjs')).ocrConfig, architectures: ['GlmOcrForConditionalGeneration'] };
assert.deepEqual(await ModelRegistry.get_model_files('org/ocr', { config: multimodal, dtype: 'fp32' }), [
    'config.json', 'onnx/embed_tokens.onnx', 'onnx/vision_encoder.onnx', 'onnx/decoder_model_merged.onnx', 'generation_config.json',
]);
