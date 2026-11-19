from test_support import load_token_chunker


def test_chunker_merge_keeps_configured_budget():
    module = load_token_chunker()
    assert module is not None
    param = module.TokenChunkerParam()
    assert param.chunk_token_size == 512
    assert module._split_text_by_pattern("alpha\nbeta", "") == ["alpha\nbeta"]
