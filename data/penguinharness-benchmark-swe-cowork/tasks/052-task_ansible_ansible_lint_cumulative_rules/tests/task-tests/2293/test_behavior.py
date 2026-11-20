import logging


def test_deprecated_noqa_tag_warns_only_once(caplog):
    from ansiblelint.skip_utils import get_rule_skips_from_line

    with caplog.at_level(logging.WARNING, logger="ansiblelint.skip_utils"):
        first = get_rule_skips_from_line("x: y  # noqa var-spacing")
        second = get_rule_skips_from_line("z: q  # noqa var-spacing")
    warnings = [record for record in caplog.records if "var-spacing" in record.getMessage()]
    assert first == second == ["jinja[spacing]"]
    assert len(warnings) == 1
