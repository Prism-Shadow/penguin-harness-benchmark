from test_support import load_token_chunker


def test_chunker_json_item_defaults_to_text():
    module = load_token_chunker()
    assert module is not None
    chunks = module._build_json_chunks([{"text": "payload"}], "")
    assert len(chunks) == 1
    assert chunks[0]["ck_type"] == "text"
    assert chunks[0]["text"] == "payload"
