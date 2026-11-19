from test_support import load_wiki


def test_wiki_document_id_normalization_is_stable():
    module = load_wiki()
    assert module is not None
    assert module._wiki_doc_ids(["d1", ["d2", "d1"], ""]) == {"d1", "d2"}
