export const ocrConfig = {
    model_type: 'glm_ocr',
    image_token_id: 71,
    text_config: {
        model_type: 'glm_ocr_text',
        hidden_size: 8,
        head_dim: 8,
        num_attention_heads: 1,
        num_key_value_heads: 1,
        num_hidden_layers: 1,
        vocab_size: 128,
    },
    vision_config: { spatial_merge_size: 2 },
};
