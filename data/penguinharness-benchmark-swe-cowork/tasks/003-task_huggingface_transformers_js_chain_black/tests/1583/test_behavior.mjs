const { api, encoderBehavior } = await import('../support/inference.mjs');
await encoderBehavior(api.AutoModelForMaskedLM, {model_type: 'eurobert', hidden_size: 8, num_hidden_layers: 1, num_attention_heads: 1}, 'input_ids', 'logits', 'EuroBertForMaskedLM');
await encoderBehavior(api.AutoModel, {model_type: 'eurobert', hidden_size: 8, num_hidden_layers: 1, num_attention_heads: 1}, 'input_ids', 'last_hidden_state', 'EuroBertModel');
