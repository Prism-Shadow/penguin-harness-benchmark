from test_support import load_wiki_incremental


def test_topic_mode_source_id_normalization_remains_deterministic():
    module = load_wiki_incremental()
    assert module is not None
    assert module._wiki_claim_chunk_ids({"chunk_ids": "c1"}) == ["c1"]
