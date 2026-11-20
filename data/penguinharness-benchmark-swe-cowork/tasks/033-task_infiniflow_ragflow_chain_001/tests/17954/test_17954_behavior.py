from test_support import load_token_chunker


def test_chunker_parameter_defaults_are_stable():
    module = load_token_chunker()
    assert module is not None
    param = module.TokenChunkerParam()
    assert param.delimiters == ["\n"]
    assert param.overlapped_percent == 0
