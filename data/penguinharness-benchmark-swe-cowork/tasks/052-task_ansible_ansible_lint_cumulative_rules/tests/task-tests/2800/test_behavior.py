from copy import deepcopy


def test_custom_prefix_is_removed_before_casing_check():
    from ansiblelint.config import options
    from ansiblelint.file_utils import Lintable
    from ansiblelint.rules import RulesCollection
    from ansiblelint.rules.name import NameRule

    local_options = deepcopy(options)
    local_options.enable_list = ["name[prefix]"]
    local_options.task_name_prefix = "{stem}: "
    collection = RulesCollection(options=local_options)
    rule = NameRule()
    collection.register(rule)
    lintable = Lintable("tasks/install.yml", content="", kind="tasks")
    matches = rule.matchtask(
        {"name": "install: Configure service", "debug": {}, "__line__": 2}, file=lintable
    )
    assert not matches
