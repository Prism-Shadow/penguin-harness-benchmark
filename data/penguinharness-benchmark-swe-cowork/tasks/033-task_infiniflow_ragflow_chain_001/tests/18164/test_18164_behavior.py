from test_support import load_wiki_incremental


def test_incremental_wiki_topic_query_contains_claim_and_source_evidence():
    module = load_wiki_incremental()
    assert module is not None
    assert callable(getattr(module, "_wiki_topic_query_text", None))
    query = module._wiki_topic_query_text(
        "Title",
        [{"statement": "Claim text"}],
        [{"text": "Source text"}],
    )
    assert "Title" in query
    assert "Claim text" in query
    assert "Source text" in query
