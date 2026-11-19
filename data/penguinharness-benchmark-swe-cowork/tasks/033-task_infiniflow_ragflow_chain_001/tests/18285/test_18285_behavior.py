from test_support import load_wiki


def test_wiki_chunk_state_delta_tracks_new_changed_deleted_and_unchanged():
    module = load_wiki()
    assert module is not None
    assert callable(getattr(module, "_wiki_compare_chunk_states", None))
    before = {"a": {"hash": "1"}, "b": {"hash": "old"}, "removed": {"hash": "gone"}}
    after = {"a": {"hash": "1"}, "b": {"hash": "new"}, "c": {"hash": "1"}}
    delta = module._wiki_compare_chunk_states(before, after)
    assert delta == {
        "new_chunk_ids": {"c"},
        "changed_chunk_ids": {"b"},
        "deleted_chunk_ids": {"removed"},
        "unchanged_chunk_ids": {"a"},
    }
