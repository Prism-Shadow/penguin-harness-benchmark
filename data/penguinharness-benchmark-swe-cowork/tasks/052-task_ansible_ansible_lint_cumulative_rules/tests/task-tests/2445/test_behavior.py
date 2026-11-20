def test_matchtasks_flattens_typed_errors_and_filters_each_tag():
    from ansiblelint.file_utils import Lintable
    from ansiblelint.rules import AnsibleLintRule

    class MultiMatchRule(AnsibleLintRule):
        id = "multi-match"
        shortdesc = "Return multiple typed task matches"
        tags = ["test"]

        def matchtask(self, task, file=None):
            return [
                self.create_matcherror(
                    message="first problem", tag="multi-match[first]", filename=file
                ),
                self.create_matcherror(
                    message="second problem", tag="multi-match[second]", filename=file
                ),
            ]

    lintable = Lintable(
        "tasks/main.yml",
        content=(
            "---\n"
            "- name: Configure service  # noqa: multi-match[second]\n"
            "  debug:\n"
            "    msg: value\n"
        ),
        kind="tasks",
    )
    matches = MultiMatchRule().matchtasks(lintable)
    assert len(matches) == 1
    assert matches[0].tag == "multi-match[first]"
    assert matches[0].message == "first problem"
    assert matches[0].filename == str(lintable.path)
    assert matches[0].lintable is lintable
    assert matches[0].details.startswith("Task/Handler:")
    assert "Configure service" in matches[0].details
