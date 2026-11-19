from test_support import load_wiki_incremental


def test_wiki_claim_source_ids_accept_scalar_and_list_forms():
    module = load_wiki_incremental()
    assert module is not None
    assert module._wiki_claim_chunk_ids({"source_chunk_id": "c1"}) == ["c1"]
    assert module._wiki_claim_chunk_ids({"chunk_ids": ["c1", "c2"]}) == ["c1", "c2"]
