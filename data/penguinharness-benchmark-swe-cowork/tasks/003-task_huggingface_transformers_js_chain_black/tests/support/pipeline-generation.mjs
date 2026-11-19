import assert from 'node:assert/strict';
import { api, causalConfig, causalSession, withModel } from './inference.mjs';
const vocab = { '[UNK]': 0, '[PAD]': 1, hello: 2, world: 3, again: 4, today: 5, tomorrow: 6 };
const tokenizer = new api.PreTrainedTokenizer({
    decoder: { type: 'WordPiece', prefix: '##', cleanup: false },
    normalizer: null, post_processor: null,
    model: { type: 'WordLevel', vocab, unk_token: '[UNK]' },
    pre_tokenizer: { type: 'Whitespace' },
    added_tokens: [{ id: 0, content: '[UNK]', special: true }, { id: 1, content: '[PAD]', special: true }],
}, { tokenizer_class: 'PreTrainedTokenizer', unk_token: '[UNK]', pad_token: '[PAD]', model_max_length: 32 });
const boundary = causalSession();
await withModel(api.AutoModelForCausalLM, causalConfig('gpt2'), {model: boundary.session}, async (model) => {
    const pipeline = new api.TextGenerationPipeline({ task: 'text-generation', model, tokenizer });
    assert.deepEqual(await pipeline('hello', {max_new_tokens: 2}), [{generated_text: 'hello world again'}]);
    assert.deepEqual(await pipeline('hello world', {max_new_tokens: 2, return_full_text: false}), [{generated_text: ' again today'}]);
    assert.deepEqual(await pipeline(['hello', 'world'], {max_new_tokens: 1}), [
        [{generated_text: 'hello world'}], [{generated_text: 'world again'}],
    ]);
    await assert.rejects(pipeline(17), /Input must be/);
});
assert.equal(boundary.releases, 1);
