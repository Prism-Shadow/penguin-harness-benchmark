from copy import deepcopy


def test_opt_in_prefix_rule_uses_task_file_stem():
    from ansiblelint.config import options
    from ansiblelint.file_utils import Lintable
    from ansiblelint.rules import RulesCollection
    from ansiblelint.rules.name import NameRule

    local_options = deepcopy(options)
    local_options.enable_list = ["name[prefix]"]
    local_options.task_name_prefix = "{stem} | "
    collection = RulesCollection(options=local_options)
    rule = NameRule()
    collection.register(rule)
    lintable = Lintable("tasks/install.yml", content="", kind="tasks")
    matches = rule.matchtask(
        {"name": "Configure service", "debug": {}, "__line__": 2}, file=lintable
    )
    matches = matches if isinstance(matches, list) else [matches]
    assert [match.tag for match in matches if match] == ["name[prefix]"]
    assert "install | " in matches[0].message
