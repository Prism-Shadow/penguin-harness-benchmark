from test_support import load_token_chunker


def test_legacy_token_size_mode_is_migrated_to_delimiter_mode():
    module = load_token_chunker()
    assert module is not None
    param = module.TokenChunkerParam()
    param.delimiter_mode = "token_size"
    param.check()
    assert param.delimiter_mode == "delimiter"
