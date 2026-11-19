def test_nested_jinja_is_reported_by_jinja_invalid_subrule():
    from ansiblelint.file_utils import Lintable
    from ansiblelint.rules.jinja import JinjaRule

    task = {
        "name": "Render invalid value",
        "debug": {"msg": "{{ {{ 'one' }} }}"},
        "__line__": 6,
    }
    match = JinjaRule().matchtask(task, Lintable("tasks/main.yml", content="", kind="tasks"))
    assert match and match.tag == "jinja[invalid]"
    assert match.rule.id == "jinja"
