from test_support import load_token_chunker


def test_chunker_sentence_take_handles_empty_input():
    module = load_token_chunker()
    assert module is not None
    assert module._take_sentences("", 2) == ""
