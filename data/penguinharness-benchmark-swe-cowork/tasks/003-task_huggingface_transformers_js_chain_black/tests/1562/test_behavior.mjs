const { causalBehavior } = await import('../support/inference.mjs');
await causalBehavior('qwen2_moe');
await causalBehavior('qwen3_next');
await causalBehavior('olmo_hybrid');
