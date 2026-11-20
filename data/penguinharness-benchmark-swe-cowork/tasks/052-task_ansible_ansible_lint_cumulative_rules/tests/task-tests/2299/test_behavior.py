def test_lintable_data_includes_ruamel_noqa_annotations():
    from ansiblelint.file_utils import Lintable

    content = "---\n- hosts: all\n  tasks:\n    - name: lowercase  # noqa name[casing]\n      debug:\n        msg: value\n"
    data = Lintable("site.yml", content=content, kind="playbook").data
    task = data[0]["tasks"][0]
    assert "name[casing]" in task["skipped_rules"]
