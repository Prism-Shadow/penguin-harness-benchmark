from test_support import load_token_chunker


def test_chunker_delimiter_pattern_is_deterministic():
    module = load_token_chunker()
    assert module is not None
    assert module._compile_delimiter_pattern(["`||`", "`|`"]) == r"\|\||\|"
