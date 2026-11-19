import pytest


@pytest.mark.parametrize("content,expected", [
    ("---\nfirst: 1\n---\nsecond: 2\n", [{"first": 1}, {"second": 2}]),
    ("---\nfirst: 1\n---\nnull\n---\nthird: 3\n", [{"first": 1}, None, {"third": 3}]),
    ("---\nnull\n---\nlast: 2\n", [None, {"last": 2}]),
    ("---\nfirst: 1\n---\nnull\n", [{"first": 1}, None]),
    ("---\n---\nlast: 3\n", [None, {"last": 3}]),
    ("---\nfirst: 1\n---\n---\nlast: 3\n", [{"first": 1}, None, {"last": 3}]),
    ("---\nfirst: 1\n---\n", [{"first": 1}, None]),
    ("---\nnull\n---\nnull\n", [None, None]),
])
def test_lintable_loads_every_yaml_document(content, expected):
    from ansiblelint.file_utils import Lintable

    file = Lintable("vars/multiple.yml", content=content, kind="yaml")
    data = file.data
    assert isinstance(data, list)
    assert len(data) == len(expected)
    for document, wanted in zip(data, expected):
        if wanted is None:
            assert document is None
        else:
            for key, value in wanted.items():
                assert document[key] == value
    assert file.data is data
