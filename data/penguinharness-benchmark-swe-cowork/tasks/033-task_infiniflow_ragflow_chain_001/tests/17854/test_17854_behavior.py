from test_support import load_token_chunker


def test_chunker_media_items_remain_atomic():
    module = load_token_chunker()
    assert module is not None
    chunks = module._build_json_chunks([{"doc_type_kwd": "table", "text": "wide"}], "")
    assert chunks[0]["ck_type"] == "table"
    assert chunks[0]["text"] == "wide"
