def test_import_playbook_statement_also_requires_a_name():
    from ansiblelint.file_utils import Lintable
    from ansiblelint.rules.name import NameRule

    lintable = Lintable("site.yml", content="", kind="playbook")
    matches = NameRule().matchplay(
        lintable, {"import_playbook": "child.yml", "__line__": 11}
    )
    assert len(matches) == 1
    assert matches[0].tag == "name[play]"
    assert matches[0].linenumber == 11
