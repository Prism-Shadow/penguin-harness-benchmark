def test_uncased_leading_character_does_not_trigger_name_casing():
    from ansiblelint.rules.name import NameRule

    result = NameRule().matchtask({"name": "1 configure service", "debug": {}, "__line__": 2})
    assert not result
