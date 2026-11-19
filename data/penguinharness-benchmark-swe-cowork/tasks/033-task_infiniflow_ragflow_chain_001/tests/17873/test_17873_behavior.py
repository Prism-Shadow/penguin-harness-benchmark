from test_support import load_token_chunker


def test_chunker_empty_delimiter_pattern_is_a_noop():
    module = load_token_chunker()
    assert module is not None
    assert module._split_text_by_pattern("one two", "") == ["one two"]
