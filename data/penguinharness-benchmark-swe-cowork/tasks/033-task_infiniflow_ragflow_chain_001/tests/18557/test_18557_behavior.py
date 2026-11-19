from test_support import load_wiki


def test_wiki_map_hash_is_deterministic_for_same_content():
    module = load_wiki()
    assert module is not None
    assert module._chunk_hash("same") == module._chunk_hash("same")
