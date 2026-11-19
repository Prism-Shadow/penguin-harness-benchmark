from test_support import load_wiki


def test_wiki_extract_helpers_return_empty_shape_for_empty_input():
    module = load_wiki()
    assert module is not None
    assert module._wiki_empty_extract() == {
        "entities": [],
        "relations": [],
        "claims": [],
        "concepts": [],
        "topics": [],
    }
