from test_support import load_wiki_incremental


def test_incremental_wiki_deduplicates_claims_by_source_identity():
    module = load_wiki_incremental()
    assert module is not None
    assert callable(getattr(module, "_wiki_dedupe_claims", None))
    claims = [
        {"statement": "A", "source_doc_id": "doc", "chunk_ids": ["c1"]},
        {"statement": "A", "source_doc_id": "doc", "chunk_ids": ["c1"]},
        {"statement": "A", "source_doc_id": "doc", "chunk_ids": ["c2"]},
    ]
    assert len(module._wiki_dedupe_claims(claims)) == 2
